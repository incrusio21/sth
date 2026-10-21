# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

"""Purchase Invoice pembayaran retensi.

Retensi tiap PI termin dipotong lewat baris taxes __from_retensi__: dikredit ke
akun retensi dengan party supplier, jadi tidak ada di outstanding PI termin. Saat
retensinya dibayar, sisa retensi semua PI termin satu Proposal ditarik ke satu PI
baru (pembayaran_retensi). PI itu mendebit akun retensi (party supplier) dan
mengkredit credit_to-nya, lalu dibayar Payment Entry seperti PI biasa.

PI lama yang retensinya masih ditahan di outstanding (tanpa baris taxes itu) tidak
ikut; retensinya dibayar lewat Payment Remaining Invoice di Proposal.
"""

import frappe
from frappe import _
from frappe.utils import flt, nowdate
from erpnext.accounts.utils import update_voucher_outstanding

from sth.custom import method_ambil_account
from sth.legal import get_legal_settings

RETENSI_MARKER = "__from_retensi__"


def get_retensi_belum_dibayar(proposal, kecuali=None):
	"""Sisa retensi per PI termin Proposal yang belum ditarik PI pembayaran retensi
	yang sudah submit. kecuali: PI pembayaran retensi yang sedang divalidasi."""
	return frappe.db.sql(
		"""
		select
			pi.name as purchase_invoice, pi.posting_date, pi.termin, pi.supplier,
			pi.company, pi.unit, pi.cost_center, pi.invoice_type,
			t.account_head as akun_retensi,
			-sum(t.tax_amount) - ifnull((
				select sum(r.amount) from `tabPurchase Invoice Retensi` r
				inner join `tabPurchase Invoice` p on p.name = r.parent
				where r.purchase_invoice = pi.name and r.akun_retensi = t.account_head
					and p.docstatus = 1 and p.name != %(kecuali)s
			), 0) as amount
		from `tabPurchase Invoice` pi
		inner join `tabPurchase Taxes and Charges` t
			on t.parent = pi.name and t.parenttype = 'Purchase Invoice'
			and t.description = %(marker)s
		where pi.docstatus = 1 and pi.is_return = 0
			and (
				exists (select 1 from `tabPurchase Invoice Item` i
					where i.parent = pi.name and i.proposal = %(proposal)s)
				or (pi.document_type = 'BAPP' and pi.document_no in (
					select b.name from `tabBAPP` b where b.proposal = %(proposal)s))
			)
		group by pi.name, t.account_head
		having amount > 0
		order by pi.posting_date, pi.name
		""",
		{"proposal": proposal, "kecuali": kecuali or "", "marker": RETENSI_MARKER},
		as_dict=True,
	)


@frappe.whitelist()
def make_pembayaran_retensi(proposal):
	"""PI baru berisi seluruh sisa retensi PI termin Proposal."""
	baris = get_retensi_belum_dibayar(proposal)
	if not baris:
		frappe.throw(_("Tidak ada retensi PI termin Proposal {0} yang belum dibayar.").format(
			frappe.bold(proposal)))

	pertama = baris[0]
	item_code = item_pembayaran_retensi()

	pi = frappe.new_doc("Purchase Invoice")
	pi.update({
		"company": pertama.company,
		"supplier": pertama.supplier,
		"unit": pertama.unit,
		"cost_center": pertama.cost_center,
		"invoice_type": pertama.invoice_type,
		"posting_date": nowdate(),
		"pembayaran_retensi": 1,
		"proposal_retensi": proposal,
		"pakai_ppn": 0,
		"retensi": 0,
	})
	for row in baris:
		pi.append("retensi_invoice", {
			"purchase_invoice": row.purchase_invoice,
			"posting_date": row.posting_date,
			"termin": row.termin,
			"akun_retensi": row.akun_retensi,
			"amount": row.amount,
		})

	total = sum(flt(row.amount) for row in baris)
	pi.append("items", {
		"item_code": item_code,
		"qty": 1,
		"rate": total,
		"expense_account": pertama.akun_retensi,
		"cost_center": pertama.cost_center,
	})

	pi.set_missing_values()
	# set_missing_values mengisi ulang akun item dari default item.
	for item in pi.items:
		item.expense_account = pertama.akun_retensi
		item.rate = total
	pi.credit_to = method_ambil_account.ambil_proposal_hutang_invoice(proposal, pi.company)

	return pi


def item_pembayaran_retensi():
	item_code = get_legal_settings("default_item_code")
	if not item_code:
		frappe.throw(_("Default Item Code di Legal Settings belum diisi, dipakai sebagai item PI pembayaran retensi."))
	return item_code


def validate_pembayaran_retensi(doc):
	"""Dipanggil sebelum validate bawaan, supaya total invoice dihitung dari baris
	retensi yang sudah dicocokkan dengan sisa retensi PI termin-nya."""
	if not doc.get("pembayaran_retensi"):
		return

	if not doc.proposal_retensi:
		frappe.throw(_("Proposal Retensi wajib diisi untuk PI pembayaran retensi."))
	if not doc.get("retensi_invoice"):
		frappe.throw(_("Tabel Retensi Invoice kosong."))

	sisa = {
		(row.purchase_invoice, row.akun_retensi): row
		for row in get_retensi_belum_dibayar(doc.proposal_retensi, kecuali=doc.name)
	}
	for row in doc.retensi_invoice:
		ada = sisa.get((row.purchase_invoice, row.akun_retensi))
		if not ada:
			frappe.throw(_("Baris {0}: retensi {1} bukan PI termin Proposal {2} atau sudah dibayar.").format(
				row.idx, frappe.bold(row.purchase_invoice), frappe.bold(doc.proposal_retensi)))
		if ada.supplier != doc.supplier or ada.company != doc.company:
			frappe.throw(_("Baris {0}: supplier/company {1} beda dengan invoice ini.").format(
				row.idx, frappe.bold(row.purchase_invoice)))
		if flt(row.amount, row.precision("amount")) > flt(ada.amount, row.precision("amount")):
			frappe.throw(_("Baris {0}: retensi {1} tinggal {2}.").format(
				row.idx, frappe.bold(row.purchase_invoice),
				frappe.format_value(ada.amount, {"fieldtype": "Currency"})))

	akun = {row.akun_retensi for row in doc.retensi_invoice}
	if len(akun) > 1:
		frappe.throw(_("Retensi yang ditarik memakai lebih dari satu akun retensi: {0}. "
			"Buat PI pembayaran retensi terpisah per akun.").format(", ".join(sorted(akun))))

	if len(doc.items) != 1:
		frappe.throw(_("PI pembayaran retensi hanya berisi satu item."))

	# Tanpa pajak: PPN/PPh sudah dihitung penuh di PI termin.
	doc.retensi = 0
	doc.pakai_ppn = 0
	doc.set("ppn", [])
	doc.set("pph_lainnya", [])
	doc.set("taxes", [t for t in doc.get("taxes") if not flt(t.tax_amount)])

	item = doc.items[0]
	item.qty = 1
	item.rate = sum(flt(row.amount) for row in doc.retensi_invoice)
	item.expense_account = akun.pop()
	doc.credit_to = method_ambil_account.ambil_proposal_hutang_invoice(doc.proposal_retensi, doc.company)


def get_gl_entries_pembayaran_retensi(doc, gl_entries):
	"""Debit akun retensi dengan party supplier, menunjuk PI termin-nya supaya
	Payment Ledger retensi PI termin itu tertutup; kredit credit_to lewat jurnal
	supplier bawaan."""
	doc.make_supplier_gl_entry(gl_entries)

	item = doc.items[0]
	for row in doc.retensi_invoice:
		gl_entries.append(doc.get_gl_dict({
			"account": row.akun_retensi,
			"party_type": "Supplier",
			"party": doc.supplier,
			"against": doc.credit_to,
			"against_voucher_type": "Purchase Invoice",
			"against_voucher": row.purchase_invoice,
			"debit": flt(row.amount),
			"debit_in_account_currency": flt(row.amount),
			"cost_center": item.cost_center or doc.cost_center,
			"remarks": _("Pembayaran retensi {0}").format(row.purchase_invoice),
		}, item=item))


def validate_cancel_pi_termin(doc):
	"""PI termin yang retensinya sudah ditarik tidak boleh di-cancel duluan."""
	if doc.get("pembayaran_retensi"):
		return

	penarik = frappe.db.sql_list(
		"""
		select distinct p.name from `tabPurchase Invoice Retensi` r
		inner join `tabPurchase Invoice` p on p.name = r.parent
		where r.purchase_invoice = %s and p.docstatus = 1
		""",
		doc.name,
	)
	if penarik:
		frappe.throw(_("Retensi invoice ini sudah ditarik PI pembayaran retensi {0}. Cancel itu dulu.").format(
			", ".join(frappe.bold(n) for n in penarik)))


def betulkan_outstanding_retensi(doc, cancel=False):
	"""Hitung ulang outstanding dari akun credit_to.

	Akun retensi bertipe Payable dan jurnalnya membawa party, jadi ERPNext membuat
	Payment Ledger Entry untuknya. Tiap PLE memanggil update_voucher_outstanding
	dengan akunnya sendiri dan yang terakhir menang: outstanding PI termin tertimpa
	sisa retensi, PI pembayaran retensi tertimpa minus retensi. Outstanding yang
	benar hanya yang di credit_to.
	"""
	invoice = []
	if doc.get("pembayaran_retensi"):
		invoice = [row.purchase_invoice for row in doc.get("retensi_invoice") or []]
	if not cancel and (
		doc.get("pembayaran_retensi")
		or any(t.description == RETENSI_MARKER and flt(t.tax_amount) for t in doc.get("taxes") or [])
	):
		invoice.append(doc.name)

	for name in dict.fromkeys(invoice):
		credit_to, supplier = frappe.db.get_value("Purchase Invoice", name, ["credit_to", "supplier"])
		update_voucher_outstanding("Purchase Invoice", name, credit_to, "Supplier", supplier)

	if doc.name in invoice:
		doc.outstanding_amount = frappe.db.get_value("Purchase Invoice", doc.name, "outstanding_amount")
