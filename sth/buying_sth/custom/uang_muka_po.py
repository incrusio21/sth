# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

"""Uang muka Purchase Order yang diperhitungkan di Purchase Invoice.

Pembayaran terhadap PO dibuat lewat `get_payment_entry_uang_muka` di
purchase_order.py: jurnalnya D: Uang Muka / K: Bank dengan `against_voucher`
Purchase Order.

Uang muka itu dipakai di invoice lewat tabel `uang_muka_po`, bukan lewat tabel
`advances` bawaan ERPNext. Alasannya: jalur `advances` merekonsiliasi uang muka
dengan cara menimpa baris Payment Entry Reference di tempat — referensinya
berpindah dari Purchase Order ke Purchase Invoice dan GL Payment Entry-nya
diposting ulang. Payment Entry harus tetap menempel pada PO yang dibayar, jadi
pengurangan hutangnya dijurnal di Purchase Invoice sendiri:

    D: Hutang Invoice (credit_to)   K: Akun Uang Muka

Karena Payment Entry tidak pernah disentuh, penjaga bawaan yang mencegah satu
uang muka terpakai dua kali ikut hilang. Penggantinya `terpakai_di_invoice_lain`
di bawah: sisa uang muka dihitung dari baris `Uang Muka Purchase Invoice` milik
invoice lain yang masih submitted. Invoice yang dibatalkan otomatis melepas
jatahnya karena docstatus barisnya ikut jadi 2.
"""

import frappe
from frappe import _
from frappe.utils import flt


def po_di_invoice(doc):
	"""Purchase Order yang disebut item-item invoice ini."""
	return sorted({item.purchase_order for item in doc.get("items") if item.get("purchase_order")})


def akun_uang_muka_pe(payment_entry, purchase_order, paid_to=None):
	"""Akun yang benar-benar terdebit saat PO itu dibayar.

	Dibaca dari GL Entry-nya, bukan dihitung ulang dari Procurement Settings,
	supaya invoice tetap mengkredit akun yang sama walau setting-nya berubah
	setelah pembayaran. paid_to dipakai kalau GL-nya tidak ketemu.
	"""
	akun = frappe.db.get_value(
		"GL Entry",
		{
			"voucher_type": "Payment Entry",
			"voucher_no": payment_entry,
			"against_voucher_type": "Purchase Order",
			"against_voucher": purchase_order,
			"debit": (">", 0),
			"is_cancelled": 0,
		},
		"account",
	)

	return akun or paid_to or frappe.db.get_value("Payment Entry", payment_entry, "paid_to")


def baris_pembayaran_po(supplier, company, purchase_orders):
	"""Baris Payment Entry Reference yang masih menunjuk ke PO-PO ini."""
	if not purchase_orders:
		return []

	return frappe.db.sql(
		"""
		select
			per.name as payment_entry_row,
			per.parent as payment_entry,
			per.reference_name as purchase_order,
			per.allocated_amount as jumlah_uang_muka,
			pe.posting_date as tanggal,
			pe.paid_to
		from `tabPayment Entry Reference` per
		inner join `tabPayment Entry` pe on pe.name = per.parent
		where per.docstatus = 1
			and per.reference_doctype = 'Purchase Order'
			and per.reference_name in %(purchase_orders)s
			and per.allocated_amount > 0
			and pe.docstatus = 1
			and pe.payment_type = 'Pay'
			and pe.party_type = 'Supplier'
			and pe.party = %(supplier)s
			and pe.company = %(company)s
		order by pe.posting_date, pe.name
		""",
		{"purchase_orders": purchase_orders, "supplier": supplier, "company": company},
		as_dict=True,
	)


def terpakai_di_invoice_lain(payment_entry_rows, kecuali=None):
	"""Berapa tiap baris uang muka sudah dipakai invoice submitted yang lain."""
	if not payment_entry_rows:
		return {}

	hasil = frappe.db.sql(
		"""
		select um.payment_entry_row, sum(um.dipakai) as dipakai
		from `tabUang Muka Purchase Invoice` um
		where um.parenttype = 'Purchase Invoice'
			and um.docstatus = 1
			and um.payment_entry_row in %(rows)s
			and um.parent != %(kecuali)s
		group by um.payment_entry_row
		""",
		{"rows": payment_entry_rows, "kecuali": kecuali or ""},
		as_dict=True,
	)

	return {row.payment_entry_row: flt(row.dipakai) for row in hasil}


def uang_muka_tersedia(doc):
	"""Uang muka PO yang masih bersisa untuk invoice ini, siap jadi baris tabel."""
	baris = baris_pembayaran_po(doc.supplier, doc.company, po_di_invoice(doc))
	if not baris:
		return []

	terpakai = terpakai_di_invoice_lain([b.payment_entry_row for b in baris], kecuali=doc.name)

	tersedia = []
	for b in baris:
		sudah = terpakai.get(b.payment_entry_row, 0.0)
		sisa = flt(b.jumlah_uang_muka) - sudah
		if sisa <= 0:
			continue

		tersedia.append(
			{
				"payment_entry": b.payment_entry,
				"payment_entry_row": b.payment_entry_row,
				"purchase_order": b.purchase_order,
				"tanggal": b.tanggal,
				"akun_uang_muka": akun_uang_muka_pe(b.payment_entry, b.purchase_order, b.paid_to),
				"jumlah_uang_muka": flt(b.jumlah_uang_muka),
				"sudah_dipakai": sudah,
				"sisa": sisa,
				"dipakai": 0,
			}
		)

	return tersedia


def isi_uang_muka_po(doc):
	"""Tarik ulang tabel uang muka.

	Alokasi otomatis berhenti di nilai invoice — sisanya menunggu invoice
	berikutnya dari PO yang sama. Angka yang sudah diketik operator
	dipertahankan selama masih muat.
	"""
	tersedia = uang_muka_tersedia(doc)

	dipakai_sebelumnya = {
		row.payment_entry_row: flt(row.dipakai) for row in doc.get("uang_muka_po") or []
	}

	doc.set("uang_muka_po", [])

	sisa_tagihan = flt(doc.get("rounded_total") or doc.grand_total)
	for row in tersedia:
		usul = dipakai_sebelumnya.get(row["payment_entry_row"], row["sisa"])
		row["dipakai"] = max(min(flt(usul), row["sisa"], sisa_tagihan), 0)
		sisa_tagihan -= row["dipakai"]

		doc.append("uang_muka_po", row)

	hitung_total_uang_muka(doc)


def hitung_total_uang_muka(doc):
	doc.total_uang_muka = flt(
		sum(flt(row.dipakai) for row in doc.get("uang_muka_po") or []),
		doc.precision("total_uang_muka"),
	)

	return doc.total_uang_muka


def validate_uang_muka_po(doc):
	"""Pastikan tiap baris masih menempel di PO-nya dan tidak melebihi sisa."""
	if not doc.get("uang_muka_po"):
		doc.total_uang_muka = 0
		return

	if doc.get("is_return"):
		frappe.throw(
			_("Uang Muka Purchase Order tidak berlaku untuk Debit Note."),
			title=_("Uang Muka PO"),
		)

	baris_pe = [row.payment_entry_row for row in doc.uang_muka_po if row.payment_entry_row]
	if len(set(baris_pe)) != len(baris_pe):
		frappe.throw(
			_("Ada pembayaran uang muka yang tercantum lebih dari sekali di tabel Uang Muka Purchase Order."),
			title=_("Uang Muka PO"),
		)

	terpakai = terpakai_di_invoice_lain(baris_pe, kecuali=doc.name)

	for row in doc.uang_muka_po:
		if not row.payment_entry_row:
			frappe.throw(
				_("Baris {0} tabel Uang Muka Purchase Order tidak menunjuk baris pembayaran mana pun. "
				  "Tarik ulang lewat tombol Ambil Uang Muka PO.").format(row.idx),
				title=_("Uang Muka PO"),
			)

		referensi = frappe.db.get_value(
			"Payment Entry Reference",
			row.payment_entry_row,
			["parent", "reference_doctype", "reference_name", "allocated_amount", "docstatus"],
			as_dict=True,
		)

		if not referensi or referensi.docstatus != 1:
			frappe.throw(
				_("Pembayaran uang muka di baris {0} sudah tidak ada atau dibatalkan.").format(row.idx),
				title=_("Uang Muka PO"),
			)

		if referensi.reference_doctype != "Purchase Order":
			frappe.throw(
				_("Payment Entry {0} sudah tidak menunjuk Purchase Order lagi, melainkan {1} {2}. "
				  "Perbaiki dulu Payment Entry-nya sebelum uang mukanya dipakai di sini.").format(
					referensi.parent, _(referensi.reference_doctype), referensi.reference_name
				),
				title=_("Uang Muka PO"),
			)

		row.payment_entry = referensi.parent
		row.purchase_order = referensi.reference_name
		row.jumlah_uang_muka = flt(referensi.allocated_amount)
		row.sudah_dipakai = terpakai.get(row.payment_entry_row, 0.0)
		row.sisa = flt(row.jumlah_uang_muka) - flt(row.sudah_dipakai)

		if not row.akun_uang_muka:
			row.akun_uang_muka = akun_uang_muka_pe(row.payment_entry, row.purchase_order)

		if not row.akun_uang_muka:
			frappe.throw(
				_("Akun uang muka untuk Payment Entry {0} tidak ketemu.").format(row.payment_entry),
				title=_("Uang Muka PO"),
			)

		if flt(row.dipakai) < 0:
			frappe.throw(
				_("Uang muka yang dipakai di baris {0} tidak boleh negatif.").format(row.idx),
				title=_("Uang Muka PO"),
			)

		if flt(row.dipakai, row.precision("dipakai")) > flt(row.sisa, row.precision("sisa")):
			frappe.throw(
				_("Uang muka yang dipakai di baris {0} ({1}) melebihi sisanya ({2}). "
				  "Payment Entry {3} sudah terpakai {4} di invoice lain.").format(
					row.idx,
					frappe.format_value(flt(row.dipakai), {"fieldtype": "Currency"}),
					frappe.format_value(flt(row.sisa), {"fieldtype": "Currency"}),
					row.payment_entry,
					frappe.format_value(flt(row.sudah_dipakai), {"fieldtype": "Currency"}),
				),
				title=_("Uang Muka PO"),
			)

	total = hitung_total_uang_muka(doc)
	tagihan = flt(doc.get("rounded_total") or doc.grand_total, doc.precision("grand_total"))

	if total > tagihan:
		frappe.throw(
			_("Total uang muka ({0}) melebihi nilai invoice ({1}).").format(
				frappe.format_value(total, {"fieldtype": "Currency"}),
				frappe.format_value(tagihan, {"fieldtype": "Currency"}),
			),
			title=_("Uang Muka PO"),
		)


def gl_entries_uang_muka(doc, gl_entries):
	"""D: hutang invoice / K: akun uang muka, sebesar yang dipakai.

	Debitnya memakai party dan `against_voucher` invoice ini sendiri supaya
	outstanding hutangnya langsung berkurang lewat payment ledger, tanpa
	menyentuh Payment Entry yang membayar PO.
	"""
	cost_center = doc.cost_center or frappe.db.get_value("Company", doc.company, "cost_center")

	for row in doc.get("uang_muka_po") or []:
		dipakai = flt(row.dipakai, row.precision("dipakai"))
		if not dipakai:
			continue

		keterangan = _("Uang muka {0} lewat {1}").format(row.purchase_order, row.payment_entry)

		gl_entries.append(
			doc.get_gl_dict(
				{
					"account": doc.credit_to,
					"party_type": "Supplier",
					"party": doc.supplier,
					"against": row.akun_uang_muka,
					"debit": dipakai,
					"debit_in_account_currency": dipakai,
					"debit_in_transaction_currency": dipakai,
					"against_voucher": doc.name,
					"against_voucher_type": doc.doctype,
					"cost_center": cost_center,
					"project": doc.project,
					"remarks": keterangan,
				},
				doc.party_account_currency,
			)
		)

		gl_entries.append(
			doc.get_gl_dict(
				{
					"account": row.akun_uang_muka,
					"against": doc.credit_to,
					"credit": dipakai,
					"credit_in_account_currency": dipakai,
					"credit_in_transaction_currency": dipakai,
					"cost_center": cost_center,
					"project": doc.project,
					"remarks": keterangan,
				}
			)
		)

	return gl_entries


def advance_yang_menunjuk_po(doc):
	"""Baris tabel `advances` yang uang mukanya sebenarnya milik Purchase Order."""
	menunjuk_po = []

	for d in doc.get("advances") or []:
		if flt(d.allocated_amount) <= 0 or d.reference_type != "Payment Entry" or not d.reference_row:
			continue

		if (
			frappe.db.get_value("Payment Entry Reference", d.reference_row, "reference_doctype")
			== "Purchase Order"
		):
			menunjuk_po.append(d)

	return menunjuk_po
