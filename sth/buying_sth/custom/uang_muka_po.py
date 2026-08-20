# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

"""Uang muka Purchase Order yang diperhitungkan di Purchase Invoice.

Pembayaran terhadap PO dibuat lewat `get_payment_entry_uang_muka` di
purchase_order.py: jurnalnya D: Uang Muka / K: Bank dengan `against_voucher`
Purchase Order.

Uang muka itu dipakai lewat tabel `advances` bawaan, tapi rekonsiliasinya tidak.
Jalur bawaan merekonsiliasi dengan cara menimpa baris Payment Entry Reference di
tempat: referensinya berpindah dari Purchase Order ke Purchase Invoice dan GL
Payment Entry-nya diposting ulang. Payment Entry harus tetap menempel pada PO
yang dibayar, jadi baris advance yang menunjuk PO dilewati di
`update_against_document_in_jv` dan pengurangan hutangnya dijurnal di invoice
sendiri:

    D: Hutang Invoice (credit_to)   K: Akun Uang Muka

Karena Payment Entry tidak pernah disentuh, `unallocated_amount`-nya tidak
pernah berkurang — penjaga bawaan yang mencegah satu uang muka terpakai dua kali
ikut hilang untuk baris-baris itu. Penggantinya `terpakai_di_invoice_lain` di
bawah: sisanya dihitung dari baris `Purchase Invoice Advance` milik invoice lain
yang masih submitted. Invoice yang dibatalkan otomatis melepas jatahnya karena
docstatus barisnya ikut jadi 2.

Advance selain uang muka PO — Journal Entry, atau Payment Entry yang tidak
menunjuk PO — tidak disentuh sama sekali dan tetap lewat jalur bawaan.
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


def referensi_pe_ke_po(reference_rows):
	"""Baris Payment Entry Reference yang menunjuk Purchase Order, dipeta per nama."""
	if not reference_rows:
		return {}

	hasil = frappe.db.sql(
		"""
		select
			per.name,
			per.parent as payment_entry,
			per.reference_name as purchase_order,
			per.allocated_amount,
			per.docstatus
		from `tabPayment Entry Reference` per
		where per.name in %(rows)s
			and per.reference_doctype = 'Purchase Order'
		""",
		{"rows": list(reference_rows)},
		as_dict=True,
	)

	return {row.name: row for row in hasil}


def pasangan_uang_muka_po(doc):
	"""Baris `advances` yang uang mukanya milik PO, berpasangan dengan data PE-nya.

	Baris advance sendiri tidak menyimpan PO mana yang dibayar — yang tahu hanya
	baris Payment Entry Reference yang ditunjuk `reference_row`. Datanya ikut
	dikembalikan supaya pemanggilnya tidak perlu query ulang.
	"""
	kandidat = [
		d
		for d in doc.get("advances") or []
		if d.reference_type == "Payment Entry" and d.reference_row
	]
	if not kandidat:
		return []

	info = referensi_pe_ke_po([d.reference_row for d in kandidat])

	return [(d, info[d.reference_row]) for d in kandidat if d.reference_row in info]


def advance_uang_muka_po(doc):
	"""Baris `advances` yang tidak boleh direkonsiliasi ke Payment Entry-nya."""
	return [baris for baris, _ in pasangan_uang_muka_po(doc)]


def terpakai_di_invoice_lain(reference_rows, kecuali=None):
	"""Berapa tiap baris uang muka sudah dipakai invoice submitted yang lain."""
	if not reference_rows:
		return {}

	hasil = frappe.db.sql(
		"""
		select pia.reference_row, sum(pia.allocated_amount) as dipakai
		from `tabPurchase Invoice Advance` pia
		where pia.parenttype = 'Purchase Invoice'
			and pia.docstatus = 1
			and pia.reference_type = 'Payment Entry'
			and pia.reference_row in %(rows)s
			and pia.parent != %(kecuali)s
		group by pia.reference_row
		""",
		{"rows": list(reference_rows), "kecuali": kecuali or ""},
		as_dict=True,
	)

	return {row.reference_row: flt(row.dipakai) for row in hasil}


def koreksi_advance_uang_muka_po(doc):
	"""Rapikan baris uang muka PO yang baru ditarik `set_advances()` bawaan.

	Bawaan mengisi advance_amount dari allocated_amount baris Payment Entry
	Reference — angka penuh, karena bawaan mengandalkan unallocated_amount
	Payment Entry yang di sini memang tidak pernah berkurang. Sisanya dipotong
	dengan yang sudah dipakai invoice lain, alokasinya dibatasi tagihan yang
	belum tertutup advance lain, dan baris yang sudah habis dibuang.
	"""
	pasangan = pasangan_uang_muka_po(doc)
	if not pasangan:
		return

	terpakai = terpakai_di_invoice_lain(
		[baris.reference_row for baris, _ in pasangan], kecuali=doc.name
	)
	uang_muka = {baris.reference_row: info for baris, info in pasangan}

	sisa_tagihan = flt(doc.get("rounded_total") or doc.grand_total)
	for baris in doc.get("advances"):
		if baris.reference_row not in uang_muka:
			sisa_tagihan -= flt(baris.allocated_amount)

	tersisa = []
	for baris in doc.get("advances"):
		info = uang_muka.get(baris.reference_row)
		if info is None:
			tersisa.append(baris)
			continue

		sisa = flt(info.allocated_amount) - terpakai.get(baris.reference_row, 0.0)
		if sisa <= 0:
			continue

		baris.advance_amount = sisa
		baris.allocated_amount = max(min(flt(baris.allocated_amount), sisa, sisa_tagihan), 0)
		sisa_tagihan -= flt(baris.allocated_amount)
		tersisa.append(baris)

	doc.set("advances", tersisa)
	for urutan, baris in enumerate(doc.get("advances"), start=1):
		baris.idx = urutan


def validate_uang_muka_po(doc):
	"""Pastikan tiap baris uang muka PO masih sah dan tidak melebihi sisanya."""
	pasangan = pasangan_uang_muka_po(doc)
	if not pasangan:
		return

	if doc.get("is_return"):
		frappe.throw(
			_("Uang muka Purchase Order tidak berlaku untuk Debit Note."),
			title=_("Uang Muka PO"),
		)

	baris_pe = [baris.reference_row for baris, _ in pasangan]
	if len(set(baris_pe)) != len(baris_pe):
		frappe.throw(
			_("Ada pembayaran uang muka yang tercantum lebih dari sekali di tabel Advances."),
			title=_("Uang Muka PO"),
		)

	terpakai = terpakai_di_invoice_lain(baris_pe, kecuali=doc.name)

	for baris, info in pasangan:
		if info.docstatus != 1:
			frappe.throw(
				_("Pembayaran uang muka di baris {0} sudah dibatalkan.").format(baris.idx),
				title=_("Uang Muka PO"),
			)

		sisa = flt(info.allocated_amount) - terpakai.get(baris.reference_row, 0.0)
		dipakai = flt(baris.allocated_amount, baris.precision("allocated_amount"))

		if dipakai < 0:
			frappe.throw(
				_("Uang muka yang dipakai di baris {0} tidak boleh negatif.").format(baris.idx),
				title=_("Uang Muka PO"),
			)

		if dipakai > flt(sisa, baris.precision("advance_amount")):
			frappe.throw(
				_("Uang muka yang dipakai di baris {0} ({1}) melebihi sisanya ({2}). "
				  "Payment Entry {3} sudah terpakai {4} di invoice lain.").format(
					baris.idx,
					frappe.format_value(dipakai, {"fieldtype": "Currency"}),
					frappe.format_value(sisa, {"fieldtype": "Currency"}),
					info.payment_entry,
					frappe.format_value(
						terpakai.get(baris.reference_row, 0.0), {"fieldtype": "Currency"}
					),
				),
				title=_("Uang Muka PO"),
			)

		if not akun_uang_muka_pe(info.payment_entry, info.purchase_order):
			frappe.throw(
				_("Akun uang muka untuk Payment Entry {0} tidak ketemu.").format(info.payment_entry),
				title=_("Uang Muka PO"),
			)

		baris.advance_amount = sisa

	# Penjaga ini sengaja hanya dipasang kalau ada uang muka PO. Kelebihan alokasi
	# advance biasa masih dicegat rekonsiliasi bawaan; uang muka PO melewati
	# rekonsiliasi itu, jadi kelebihannya baru ketahuan sebagai jurnal yang lebih
	# besar dari tagihan dan outstanding minus.
	total_advance = flt(doc.total_advance, doc.precision("total_advance"))
	tagihan = flt(doc.get("rounded_total") or doc.grand_total, doc.precision("grand_total"))

	if total_advance > tagihan:
		frappe.throw(
			_("Total advance ({0}), termasuk uang muka Purchase Order, melebihi nilai invoice ({1}).").format(
				frappe.format_value(total_advance, {"fieldtype": "Currency"}),
				frappe.format_value(tagihan, {"fieldtype": "Currency"}),
			),
			title=_("Uang Muka PO"),
		)


def gl_entries_uang_muka(doc, gl_entries):
	"""D: hutang invoice / K: akun uang muka, sebesar yang dialokasikan.

	Debitnya memakai party dan `against_voucher` invoice ini sendiri supaya
	outstanding hutangnya langsung berkurang lewat payment ledger, tanpa
	menyentuh Payment Entry yang membayar PO. Mengembalikan jumlah baris jurnal
	yang ditambahkan.
	"""
	pasangan = pasangan_uang_muka_po(doc)
	if not pasangan:
		return 0

	cost_center = doc.cost_center or frappe.db.get_value("Company", doc.company, "cost_center")
	ditambahkan = 0

	for baris, info in pasangan:
		dipakai = flt(baris.allocated_amount, baris.precision("allocated_amount"))
		if not dipakai:
			continue

		akun_uang_muka = akun_uang_muka_pe(info.payment_entry, info.purchase_order)
		keterangan = _("Uang muka {0} lewat {1}").format(info.purchase_order, info.payment_entry)

		gl_entries.append(
			doc.get_gl_dict(
				{
					"account": doc.credit_to,
					"party_type": "Supplier",
					"party": doc.supplier,
					"against": akun_uang_muka,
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
					"account": akun_uang_muka,
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

		ditambahkan += 2

	return ditambahkan
