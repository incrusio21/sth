import frappe

from sth.custom.method_ambil_account import (
	ambil_proposal_hutang_invoice,
	ambil_proposal_hutang_usaha,
	ambil_proposal_uang_muka,
)
from sth.overrides.purchase_invoice import proposal_bapp_purchase_invoice
from sth.patches.koreksi_akun_persediaan_purchase_receipt import accounting_period_tertutup

DOCTYPE = "Purchase Invoice"


def execute(purchase_invoice=None, company=None, dari=None, sampai=None, dry_run=True):
	"""Pindahkan akun Purchase Invoice BAPP ke akun Proposal Type-nya.

	BAPP Item tidak membawa link proposal, jadi validate() Purchase Invoice tidak
	pernah memakai akun proposal untuk invoice BAPP:

	    - credit_to tertimpa akun party begitu supplier terisi di form, biasanya
	      default payable Company (mis. 2111091 - HUTANG INVOICE - PEMASOK),
	      bukan Hutang Invoice Proposal Type (mis. 2111092 - HUTANG INVOICE -
	      KONTRAKTOR)
	    - expense_account item jatuh ke akun biaya bawaan item. Biaya itu sudah
	      dijurnal BAPP dengan lawan Hutang Usaha Proposal Type (mis. 2111002 -
	      HUTANG USAHA - KONTRAKTOR), jadi biayanya tercatat dua kali dan Hutang
	      Usaha itu tidak pernah tertutup. Termin DP memakai Uang Muka Proposal
	      Type.

	Yang dipindah untuk invoice submit, semuanya cuma ganti akun - nilai debit
	dan kredit tidak bergerak:

	    - credit_to, serta baris GL dan Payment Ledger Entry hutang invoice itu,
	      termasuk potongan uang muka PO yang dibukukan di voucher invoice itu
	    - expense_account item, serta baris debit GL item itu (voucher_detail_no)

	Invoice draft cukup diganti credit_to dan expense_account-nya.

	Yang dilewati dan cuma dicetak:

	    - credit_to invoice yang sudah dibayar atau dikurangi dokumen lain
	      (Payment Entry, Journal Entry, Debit Note): akun dokumen itu ikut harus
	      dipindah, dan itu diputuskan tangan. expense_account-nya tetap dipindah.
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
		print("Akun Purchase Invoice BAPP: tidak ada dokumen yang diproses")
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
		 "termin", "document_type", "document_no"],
		as_dict=True,
	)

	if not pi:
		return False, "dokumen tidak ada"

	if pi.docstatus == 2:
		return False, "sudah dibatalkan"

	proposal = proposal_bapp_purchase_invoice(pi)
	if not proposal:
		return False, f"BAPP {pi.document_no} tidak punya Proposal"

	ambil_biaya = ambil_proposal_uang_muka if pi.termin == "DP" else ambil_proposal_hutang_usaha

	try:
		hutang_baru = ambil_proposal_hutang_invoice(proposal, pi.company)
		biaya_baru = ambil_biaya(proposal, pi.company)
	except frappe.ValidationError:
		frappe.clear_messages()
		return False, f"Proposal Type {proposal} belum lengkap akunnya untuk {pi.company}"

	items = frappe.get_all(
		"Purchase Invoice Item",
		filters={"parent": nama, "parenttype": DOCTYPE},
		fields=["name", "expense_account"],
		order_by="idx",
	)
	item_salah = [d for d in items if d.expense_account != biaya_baru]

	hutang_lama = pi.credit_to
	pindah_hutang = hutang_lama != hutang_baru

	if not pindah_hutang and not item_salah:
		return False, ""

	if pi.docstatus == 1 and pi.is_return:
		return False, "Debit Note, pindahkan bersama invoice asalnya dengan tangan"

	if pi.docstatus == 1:
		periode = accounting_period_tertutup(pi.posting_date, pi.company)
		if periode:
			return False, f"Accounting Period {periode} sudah disubmit"

	pesan = []
	catatan = ""

	if pindah_hutang and pi.docstatus == 1:
		lain = dokumen_lain_terhadap_invoice(nama)
		if lain:
			pindah_hutang = False
			catatan = f"; credit_to {hutang_lama} dilewati, sudah ada dokumen lain: " + ", ".join(lain)

	if pindah_hutang:
		pesan.append(f"credit_to {hutang_lama} -> {hutang_baru}")

	if item_salah:
		lama = ", ".join(sorted({d.expense_account or "-" for d in item_salah}))
		pesan.append(f"expense_account {lama} -> {biaya_baru} ({len(item_salah)} baris)")

	if not pesan:
		return False, catatan.lstrip("; ")

	pesan = "; ".join(pesan) + catatan

	if pi.docstatus == 0:
		pesan += " (draft)"

	if dry_run:
		return True, pesan

	if pindah_hutang:
		frappe.db.set_value(DOCTYPE, nama, "credit_to", hutang_baru, update_modified=False)
		if pi.docstatus == 1:
			_pindahkan_ledger_hutang(nama, hutang_lama, hutang_baru)

	if item_salah:
		against_lama = _gabung_akun(d.expense_account for d in items)

		for d in item_salah:
			frappe.db.set_value("Purchase Invoice Item", d.name, "expense_account", biaya_baru, update_modified=False)

			if pi.docstatus == 1:
				_pindahkan_ledger_biaya(nama, d, biaya_baru)

		if pi.docstatus == 1:
			# Baris hutang mencatat gabungan expense_account semua item sebagai
			# against-nya (make_item_gl_entries_spk).
			against_baru = _gabung_akun(
				biaya_baru if d in item_salah else d.expense_account for d in items
			)
			frappe.db.sql(
				"""
				update `tabGL Entry`
				set against = %s
				where voucher_type = %s and voucher_no = %s and is_cancelled = 0 and against = %s
				""",
				(against_baru, DOCTYPE, nama, against_lama),
			)

	return True, pesan


def _gabung_akun(akun):
	return ", ".join(sorted({a for a in akun if a}))


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


def _pindahkan_ledger_biaya(nama, item, akun_baru):
	"""Baris debit GL satu item invoice ke akun baru, dikenali dari voucher_detail_no."""
	frappe.db.sql(
		"""
		update `tabGL Entry`
		set account = %s
		where voucher_type = %s and voucher_no = %s and is_cancelled = 0
		  and voucher_detail_no = %s and account = %s
		""",
		(akun_baru, DOCTYPE, nama, item.name, item.expense_account),
	)


def _pindahkan_ledger_hutang(nama, akun_lama, akun_baru):
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
	print(f"=== Akun Purchase Invoice BAPP ke akun Proposal Type - {judul} ===")

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
