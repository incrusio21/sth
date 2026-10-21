import frappe

from sth.custom.method_ambil_account import ambil_proposal_hutang_invoice
from sth.overrides.purchase_invoice import proposal_bapp_purchase_invoice
from sth.patches.koreksi_akun_persediaan_purchase_receipt import accounting_period_tertutup

DOCTYPE = "Purchase Invoice"


def execute(purchase_invoice=None, company=None, dari=None, sampai=None, dry_run=True):
	"""Pindahkan hutang Purchase Invoice BAPP ke akun Hutang Invoice Proposal Type.

	BAPP Item tidak membawa link proposal, jadi validate() Purchase Invoice tidak
	pernah menetapkan credit_to invoice BAPP. Akun dari make_purchase_invoice BAPP
	tertimpa form begitu supplier terisi, dan yang tersimpan akun party - biasanya
	default payable Company (mis. 2111091 - HUTANG INVOICE - PEMASOK) - bukan
	akun Hutang Invoice di Proposal Type (mis. 2111092 - HUTANG INVOICE -
	KONTRAKTOR).

	Yang dipindah untuk invoice submit, semuanya cuma ganti akun - nilai debit
	dan kredit tidak bergerak:

	    - credit_to di Purchase Invoice
	    - baris GL dan Payment Ledger Entry hutang invoice itu, termasuk potongan
	      uang muka PO yang dibukukan di voucher invoice itu sendiri

	Invoice draft cukup diganti credit_to-nya.

	Yang dilewati dan cuma dicetak:

	    - invoice yang sudah dibayar atau dikurangi dokumen lain (Payment Entry,
	      Journal Entry, Debit Note): akun dokumen itu ikut harus dipindah, dan
	      itu diputuskan tangan
	    - Debit Note (is_return): ikut invoice asalnya
	    - invoice yang tanggalnya masuk Accounting Period yang sudah disubmit

	    from sth.patches.pindahkan_hutang_purchase_invoice_bapp import execute
	    execute(company="PT. TRIMITRA LESTARI")
	    execute(["ACC-PINV-2026-00145"], dry_run=False)

	Default-nya dry run: mencetak rencana per dokumen, tanpa menulis apa pun.
	"""
	if isinstance(purchase_invoice, str):
		purchase_invoice = [purchase_invoice]

	daftar = purchase_invoice or cari_purchase_invoice(company, dari, sampai)

	if not daftar:
		print("Hutang Purchase Invoice BAPP: tidak ada dokumen yang diproses")
		return

	berhasil, dilewati = [], []

	for nama in daftar:
		hasil, pesan = _proses_satu(nama, dry_run)

		if hasil:
			berhasil.append((nama, pesan))
			if not dry_run:
				frappe.db.commit()
		elif pesan:
			dilewati.append((nama, pesan))

	_cetak_ringkasan(berhasil, dilewati, dry_run)


def cari_purchase_invoice(company=None, dari=None, sampai=None):
	"""Purchase Invoice dari BAPP yang belum dibatalkan.

	Akun yang benar baru bisa dihitung per invoice (Proposal BAPP -> Proposal
	Type), jadi yang sudah benar disaring di _proses_satu.
	"""
	syarat = [
		"pi.docstatus < 2",
		"pi.document_type = 'BAPP'",
		"ifnull(pi.document_no, '') != ''",
	]
	nilai = {}

	if company:
		syarat.append("pi.company = %(company)s")
		nilai["company"] = company

	if dari:
		syarat.append("pi.posting_date >= %(dari)s")
		nilai["dari"] = dari

	if sampai:
		syarat.append("pi.posting_date <= %(sampai)s")
		nilai["sampai"] = sampai

	return frappe.db.sql_list(
		"""
		select pi.name
		from `tabPurchase Invoice` pi
		where {}
		order by pi.posting_date, pi.name
		""".format(" and ".join(syarat)),
		nilai,
	)


def _proses_satu(nama, dry_run):
	"""(berhasil, pesan). Pesan kosong berarti sudah benar, tidak perlu dicetak."""
	pi = frappe.db.get_value(
		DOCTYPE,
		nama,
		["name", "company", "posting_date", "docstatus", "is_return", "credit_to",
		 "document_type", "document_no"],
		as_dict=True,
	)

	if not pi:
		return False, "dokumen tidak ada"

	if pi.docstatus == 2:
		return False, "sudah dibatalkan"

	proposal = proposal_bapp_purchase_invoice(pi)
	if not proposal:
		return False, f"BAPP {pi.document_no} tidak punya Proposal"

	try:
		akun_baru = ambil_proposal_hutang_invoice(proposal, pi.company)
	except frappe.ValidationError:
		frappe.clear_messages()
		return False, f"Proposal Type {proposal} belum punya Hutang Invoice untuk {pi.company}"

	akun_lama = pi.credit_to

	if akun_lama == akun_baru:
		return False, ""

	pesan = f"{akun_lama} -> {akun_baru}"

	if pi.docstatus == 0:
		if not dry_run:
			frappe.db.set_value(DOCTYPE, nama, "credit_to", akun_baru, update_modified=False)

		return True, pesan + " (draft)"

	if pi.is_return:
		return False, "Debit Note, pindahkan bersama invoice asalnya dengan tangan"

	lain = dokumen_lain_terhadap_invoice(nama)
	if lain:
		return False, "sudah ada dokumen lain terhadap invoice ini: " + ", ".join(lain)

	periode = accounting_period_tertutup(pi.posting_date, pi.company)
	if periode:
		return False, f"Accounting Period {periode} sudah disubmit"

	if dry_run:
		return True, pesan

	frappe.db.set_value(DOCTYPE, nama, "credit_to", akun_baru, update_modified=False)
	_pindahkan_ledger(nama, akun_lama, akun_baru)

	return True, pesan


def dokumen_lain_terhadap_invoice(nama):
	"""Dokumen selain invoice ini yang mengurangi hutangnya."""
	return frappe.db.sql_list(
		"""
		select distinct voucher_no
		from `tabPayment Ledger Entry`
		where against_voucher_type = %s and against_voucher_no = %s
		  and delinked = 0 and voucher_no != %s
		""",
		(DOCTYPE, nama, nama),
	)


def _pindahkan_ledger(nama, akun_lama, akun_baru):
	"""Akun baris hutang GL dan Payment Ledger Entry invoice ini ke akun baru."""
	frappe.db.sql(
		"""
		update `tabGL Entry`
		set account = %s
		where voucher_type = %s and voucher_no = %s and is_cancelled = 0
		  and account = %s and against_voucher_type = %s and against_voucher = %s
		""",
		(akun_baru, DOCTYPE, nama, akun_lama, DOCTYPE, nama),
	)

	# Kolom against di baris lawan masih menyebut akun lama; ikut ditulis supaya
	# buku besar tidak menunjuk akun yang sudah tidak dipakai dokumen ini.
	frappe.db.sql(
		"""
		update `tabGL Entry`
		set against = %s
		where voucher_type = %s and voucher_no = %s and is_cancelled = 0 and against = %s
		""",
		(akun_baru, DOCTYPE, nama, akun_lama),
	)

	frappe.db.sql(
		"""
		update `tabPayment Ledger Entry`
		set account = %s
		where voucher_type = %s and voucher_no = %s and delinked = 0
		  and account = %s and against_voucher_type = %s and against_voucher_no = %s
		""",
		(akun_baru, DOCTYPE, nama, akun_lama, DOCTYPE, nama),
	)


def _cetak_ringkasan(berhasil, dilewati, dry_run):
	judul = "RENCANA (dry run)" if dry_run else "HASIL"

	print("")
	print(f"=== Hutang Purchase Invoice BAPP ke akun Proposal Type - {judul} ===")

	print("")
	print(f"Dipindahkan: {len(berhasil)}")
	for nama, pesan in berhasil:
		print(f"  {nama}: {pesan}")

	print("")
	print(f"Dilewati: {len(dilewati)}")
	for nama, pesan in dilewati:
		print(f"  {nama}: {pesan}")

	if dry_run and berhasil:
		print("")
		print("Jalankan ulang dengan dry_run=False untuk menulis.")
