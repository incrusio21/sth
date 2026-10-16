import frappe

from sth.patches.koreksi_akun_persediaan_purchase_receipt import accounting_period_tertutup

DOCTYPE = "Journal Entry"
REMARK = "Selisih Timbang Customer - "


def execute(journal_entry=None, company=None, dari=None, sampai=None, akun=None, dry_run=True):
	"""Pindahkan baris debit Journal Entry selisih timbang ke expense account.

	JE ini dibuat on_submit Sales Invoice Pengiriman (create_timbang_journal_entry):
	nilai GL Delivery Note dipindah dari akun stock in transit. Baris debitnya dulu
	memakai income_account item pertama invoice, padahal yang benar expense_account
	item itu — sama dengan kode sekarang.

	Yang dipindah untuk JE submit, semuanya cuma ganti akun - nilai debit dan
	kredit tidak bergerak:

	    - account baris debit di Journal Entry Account
	    - baris GL Entry debitnya
	    - kolom against di baris lawan (JE Account dan GL Entry)

	Akun tujuan bawaannya expense_account item pertama invoice. Isi akun untuk
	memaksa satu akun yang sama ke semua JE, misalnya kalau expense_account
	invoicenya ikut tersalin dari Delivery Note (akun stock in transit).

	Yang dilewati dan cuma dicetak:

	    - JE yang Sales Invoice-nya sudah dibatalkan atau tidak ketemu
	    - baris debitnya bukan income_account invoice: sudah dikoreksi atau
	      diubah tangan, jadi diputuskan tangan
	    - akun tujuan kosong, sama dengan akun kreditnya, atau mata uangnya beda
	    - tanggal JE masuk Accounting Period yang sudah disubmit

	    from sth.patches.koreksi_akun_je_selisih_timbang import execute
	    execute(company="PT. TRIMITRA LESTARI")
	    execute(company="PT. TRIMITRA LESTARI", dry_run=False)
	    execute(["ACC-JV-2026-00012"], akun="5110001 - HPP CPO - TL", dry_run=False)

	Default-nya dry run: mencetak rencana per dokumen, tanpa menulis apa pun.
	"""
	if akun and not frappe.db.exists("Account", {"name": akun, "is_group": 0}):
		print(f"Akun {akun} tidak ada atau berupa grup")
		return

	daftar = journal_entry or cari_journal_entry(company, dari, sampai)

	if not daftar:
		print("JE selisih timbang: tidak ada dokumen yang diproses")
		return

	berhasil, dilewati = [], []

	for nama in daftar:
		hasil, pesan = _proses_satu(nama, akun, dry_run)

		if hasil:
			berhasil.append((nama, pesan))
			if not dry_run:
				frappe.db.commit()
		else:
			dilewati.append((nama, pesan))

	_cetak_ringkasan(berhasil, dilewati, dry_run)


def cari_journal_entry(company=None, dari=None, sampai=None):
	"""JE selisih timbang submit, dikenali dari user_remark-nya."""
	syarat = [
		"je.docstatus = 1",
		"je.user_remark like %(remark)s",
	]
	nilai = {"remark": REMARK + "%"}

	if company:
		syarat.append("je.company = %(company)s")
		nilai["company"] = company

	if dari:
		syarat.append("je.posting_date >= %(dari)s")
		nilai["dari"] = dari

	if sampai:
		syarat.append("je.posting_date <= %(sampai)s")
		nilai["sampai"] = sampai

	return frappe.db.sql_list(
		"""
		select je.name
		from `tabJournal Entry` je
		where {}
		order by je.posting_date, je.name
		""".format(" and ".join(syarat)),
		nilai,
	)


def _proses_satu(nama, akun, dry_run):
	je = frappe.db.get_value(
		DOCTYPE,
		nama,
		["name", "company", "posting_date", "docstatus", "user_remark", "sales_invoice"],
		as_dict=True,
	)

	if not je:
		return False, "dokumen tidak ada"

	if je.docstatus != 1:
		return False, "bukan JE submit"

	if not (je.user_remark or "").startswith(REMARK):
		return False, "bukan JE selisih timbang"

	si_name = je.sales_invoice or je.user_remark[len(REMARK):].strip()
	si = frappe.db.get_value("Sales Invoice", si_name, ["name", "docstatus"], as_dict=True)

	if not si:
		return False, f"Sales Invoice {si_name} tidak ada"

	if si.docstatus != 1:
		return False, f"Sales Invoice {si_name} tidak submit, JE ini seharusnya ikut dibatalkan"

	item = frappe.db.get_value(
		"Sales Invoice Item",
		{"parent": si.name, "parenttype": "Sales Invoice"},
		["income_account", "expense_account"],
		as_dict=True,
		order_by="idx asc",
	)

	baris = frappe.db.get_all(
		"Journal Entry Account",
		filters={"parent": nama, "parenttype": DOCTYPE},
		fields=["name", "account", "account_currency", "debit_in_account_currency", "credit_in_account_currency"],
	)
	debit = [b for b in baris if b.debit_in_account_currency]
	kredit = [b for b in baris if b.credit_in_account_currency]

	if len(debit) != 1:
		return False, f"baris debitnya {len(debit)}, bukan 1"

	akun_lama = debit[0].account
	akun_baru = akun or (item and item.expense_account)

	if not akun_baru:
		return False, f"expense_account item pertama {si.name} kosong"

	if akun_lama == akun_baru:
		return False, f"sudah di akun yang benar ({akun_baru})"

	if not item or akun_lama != item.income_account:
		return False, f"akun debit {akun_lama} bukan income_account {si.name}, periksa tangan"

	if akun_baru in {b.account for b in kredit}:
		return False, f"akun tujuan {akun_baru} sama dengan akun kreditnya, isi akun= untuk memaksa akun HPP"

	tujuan = frappe.db.get_value("Account", akun_baru, ["company", "is_group", "account_currency"], as_dict=True)

	if not tujuan or tujuan.is_group or tujuan.company != je.company:
		return False, f"akun tujuan {akun_baru} bukan akun ledger {je.company}"

	if tujuan.account_currency != debit[0].account_currency:
		return False, f"mata uang {akun_baru} ({tujuan.account_currency}) beda dengan {akun_lama}"

	periode = accounting_period_tertutup(je.posting_date, je.company)
	if periode:
		return False, f"Accounting Period {periode} sudah disubmit"

	pesan = f"{akun_lama} -> {akun_baru} ({si.name})"

	if dry_run:
		return True, pesan

	frappe.db.set_value("Journal Entry Account", debit[0].name, "account", akun_baru, update_modified=False)

	# Kolom against di baris lawan masih menyebut akun lama
	frappe.db.sql(
		"""
		update `tabJournal Entry Account`
		set against_account = %s
		where parent = %s and parenttype = %s and against_account = %s
		""",
		(akun_baru, nama, DOCTYPE, akun_lama),
	)

	frappe.db.sql(
		"""
		update `tabGL Entry`
		set account = %s
		where voucher_type = %s and voucher_no = %s and is_cancelled = 0
		  and account = %s and debit > 0
		""",
		(akun_baru, DOCTYPE, nama, akun_lama),
	)

	frappe.db.sql(
		"""
		update `tabGL Entry`
		set against = %s
		where voucher_type = %s and voucher_no = %s and is_cancelled = 0 and against = %s
		""",
		(akun_baru, DOCTYPE, nama, akun_lama),
	)

	return True, pesan


def _cetak_ringkasan(berhasil, dilewati, dry_run):
	judul = "RENCANA (dry run)" if dry_run else "HASIL"

	print("")
	print(f"=== Koreksi akun JE selisih timbang - {judul} ===")

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
