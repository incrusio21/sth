import frappe

from sth.patches.koreksi_akun_persediaan_purchase_receipt import accounting_period_tertutup
from sth.sales_sth.custom.sales_invoice import AKUN_PIUTANG_TIMBANGAN_MANUAL

DOCTYPE = "Sales Invoice"


def execute(sales_invoice=None, company=None, dari=None, sampai=None, dry_run=True):
	"""Pindahkan piutang Sales Invoice Timbangan Manual ke akun 1132003.

	Sejak commit f308354c invoice yang dibuat Timbangan company Manual Timbangan
	(timbangan_ref dan delivery_order terisi) memakai debit_to 1132003 - PIUTANG
	USAHA - TBS. Yang dibuat sebelumnya masih di piutang default Customer atau
	Company.

	Yang dipindah untuk invoice submit, semuanya cuma ganti akun - nilai debit
	dan kredit tidak bergerak:

	    - debit_to di Sales Invoice
	    - baris GL dan Payment Ledger Entry piutang invoice itu
	    - baris piutang Journal Entry DP yang dibuat on_submit invoice itu
	      (create_dp_payment_journal_entry): Journal Entry Account, GL, dan
	      Payment Ledger Entry-nya, supaya outstanding invoice tetap benar

	Invoice draft cukup diganti debit_to-nya.

	Yang dilewati dan cuma dicetak:

	    - invoice yang sudah dilunasi atau dikurangi dokumen lain (Payment Entry,
	      Journal Entry selain JE DP-nya, Credit Note): akun dokumen itu ikut
	      harus dipindah, dan itu diputuskan tangan
	    - invoice atau JE DP yang tanggalnya masuk Accounting Period yang sudah
	      disubmit

	    from sth.patches.pindahkan_piutang_sales_invoice_timbangan_manual import execute
	    execute(company="PT. TRIMITRA LESTARI")
	    execute(company="PT. TRIMITRA LESTARI", dry_run=False)
	    execute(["ACC-SINV-2026-00012"], dry_run=False)

	Default-nya dry run: mencetak rencana per dokumen, tanpa menulis apa pun.
	"""
	daftar = sales_invoice or cari_sales_invoice(company, dari, sampai)

	if not daftar:
		print("Piutang Sales Invoice Timbangan Manual: tidak ada dokumen yang diproses")
		return

	berhasil, dilewati = [], []

	for nama in daftar:
		hasil, pesan = _proses_satu(nama, dry_run)

		if hasil:
			berhasil.append((nama, pesan))
			if not dry_run:
				frappe.db.commit()
		else:
			dilewati.append((nama, pesan))

	_cetak_ringkasan(berhasil, dilewati, dry_run)


def cari_sales_invoice(company=None, dari=None, sampai=None):
	"""Sales Invoice dari Timbangan yang debit_to-nya belum 1132003."""
	syarat = [
		"si.docstatus < 2",
		"si.is_return = 0",
		"ifnull(si.timbangan_ref, '') != ''",
		"ifnull(si.delivery_order, '') != ''",
		"ifnull(a.account_number, '') != %(nomor)s",
	]
	nilai = {"nomor": AKUN_PIUTANG_TIMBANGAN_MANUAL}

	if company:
		syarat.append("si.company = %(company)s")
		nilai["company"] = company

	if dari:
		syarat.append("si.posting_date >= %(dari)s")
		nilai["dari"] = dari

	if sampai:
		syarat.append("si.posting_date <= %(sampai)s")
		nilai["sampai"] = sampai

	return frappe.db.sql_list(
		"""
		select si.name
		from `tabSales Invoice` si
		left join `tabAccount` a on a.name = si.debit_to
		where {}
		order by si.posting_date, si.name
		""".format(" and ".join(syarat)),
		nilai,
	)


def _proses_satu(nama, dry_run):
	si = frappe.db.get_value(
		DOCTYPE,
		nama,
		["name", "company", "posting_date", "docstatus", "is_return", "debit_to",
		 "timbangan_ref", "delivery_order", "dp_journal_entry"],
		as_dict=True,
	)

	if not si:
		return False, "dokumen tidak ada"

	if si.docstatus == 2:
		return False, "sudah dibatalkan"

	if si.is_return:
		return False, "Credit Note, bukan invoice Timbangan"

	if not (si.timbangan_ref and si.delivery_order):
		return False, "bukan invoice Timbangan Manual (timbangan_ref/delivery_order kosong)"

	akun_baru = frappe.db.get_value(
		"Account",
		{"account_number": AKUN_PIUTANG_TIMBANGAN_MANUAL, "company": si.company, "is_group": 0},
		"name",
	)

	if not akun_baru:
		return False, f"akun {AKUN_PIUTANG_TIMBANGAN_MANUAL} tidak ada di {si.company}"

	akun_lama = si.debit_to

	if akun_lama == akun_baru:
		return False, f"sudah di akun yang benar ({akun_baru})"

	pesan = f"{akun_lama} -> {akun_baru}"

	if si.docstatus == 0:
		if not dry_run:
			frappe.db.set_value(DOCTYPE, nama, "debit_to", akun_baru, update_modified=False)

		return True, pesan + " (draft)"

	je_dp = je_dp_sales_invoice(si)

	lain = dokumen_lain_terhadap_invoice(nama, je_dp)
	if lain:
		return False, "sudah ada dokumen lain terhadap invoice ini: " + ", ".join(lain)

	periode = accounting_period_tertutup(si.posting_date, si.company)
	if periode:
		return False, f"Accounting Period {periode} sudah disubmit"

	if je_dp:
		je_tanggal = frappe.db.get_value("Journal Entry", je_dp, "posting_date")
		periode = accounting_period_tertutup(je_tanggal, si.company)
		if periode:
			return False, f"JE DP {je_dp} masuk Accounting Period {periode} yang sudah disubmit"

		pesan += f", ikut JE DP {je_dp}"

	if dry_run:
		return True, pesan

	frappe.db.set_value(DOCTYPE, nama, "debit_to", akun_baru, update_modified=False)
	_pindahkan_ledger(DOCTYPE, nama, nama, akun_lama, akun_baru)

	if je_dp:
		frappe.db.sql(
			"""
			update `tabJournal Entry Account`
			set account = %s
			where parent = %s and parenttype = 'Journal Entry' and account = %s
			  and reference_type = %s and reference_name = %s
			""",
			(akun_baru, je_dp, akun_lama, DOCTYPE, nama),
		)
		_pindahkan_ledger("Journal Entry", je_dp, nama, akun_lama, akun_baru)

	return True, pesan


def je_dp_sales_invoice(si):
	"""Journal Entry DP yang dibuat on_submit invoice ini, kalau ada.

	Dicari sama dengan cancel_dp_payment_journal_entry: field dp_journal_entry
	dulu, lalu user_remark-nya.
	"""
	if si.dp_journal_entry and frappe.db.get_value("Journal Entry", si.dp_journal_entry, "docstatus") == 1:
		return si.dp_journal_entry

	return frappe.db.get_value(
		"Journal Entry",
		{"user_remark": f"Pembayaran DP Sales Invoice - {si.name}", "docstatus": 1},
		"name",
	)


def dokumen_lain_terhadap_invoice(nama, je_dp):
	"""Dokumen selain invoice ini dan JE DP-nya yang mengurangi piutangnya."""
	dikenal = [nama] + ([je_dp] if je_dp else [])

	return frappe.db.sql_list(
		"""
		select distinct voucher_no
		from `tabPayment Ledger Entry`
		where against_voucher_type = %s and against_voucher_no = %s
		  and delinked = 0 and voucher_no not in %s
		""",
		(DOCTYPE, nama, dikenal),
	)


def _pindahkan_ledger(voucher_type, voucher_no, sales_invoice, akun_lama, akun_baru):
	"""Akun baris piutang GL dan Payment Ledger Entry satu voucher ke akun baru.

	Cuma baris yang menunjuk invoice ini (against_voucher), jadi baris lain di JE
	DP - akun uang muka - tidak ikut tersentuh.
	"""
	frappe.db.sql(
		"""
		update `tabGL Entry`
		set account = %s
		where voucher_type = %s and voucher_no = %s and is_cancelled = 0
		  and account = %s and against_voucher_type = %s and against_voucher = %s
		""",
		(akun_baru, voucher_type, voucher_no, akun_lama, DOCTYPE, sales_invoice),
	)

	# Kolom against di baris lawan masih menyebut akun lama; ikut ditulis supaya
	# buku besar tidak menunjuk akun yang sudah tidak dipakai dokumen ini.
	frappe.db.sql(
		"""
		update `tabGL Entry`
		set against = %s
		where voucher_type = %s and voucher_no = %s and is_cancelled = 0 and against = %s
		""",
		(akun_baru, voucher_type, voucher_no, akun_lama),
	)

	frappe.db.sql(
		"""
		update `tabPayment Ledger Entry`
		set account = %s
		where voucher_type = %s and voucher_no = %s and delinked = 0
		  and account = %s and against_voucher_type = %s and against_voucher_no = %s
		""",
		(akun_baru, voucher_type, voucher_no, akun_lama, DOCTYPE, sales_invoice),
	)


def _cetak_ringkasan(berhasil, dilewati, dry_run):
	judul = "RENCANA (dry run)" if dry_run else "HASIL"

	print("")
	print(f"=== Piutang Sales Invoice Timbangan Manual ke {AKUN_PIUTANG_TIMBANGAN_MANUAL} - {judul} ===")

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
