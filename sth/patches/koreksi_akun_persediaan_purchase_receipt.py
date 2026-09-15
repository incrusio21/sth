import frappe

DOCTYPE = "Purchase Receipt"


def execute(purchase_receipt=None, company=None, dari=None, sampai=None, dry_run=True):
	"""Pindahkan jurnal persediaan Purchase Receipt ke akun kelompok barangnya.

	Akun persediaan per kelompok barang cuma dipakai kalau company-nya terdaftar
	aktif di Procurement Valuation Rate Settings. Selama sakelar itu mati, GL
	Purchase Receipt jatuh ke jalur ERPNext biasa dan mendebit akun milik GUDANG
	- di PT. TRIMITRA LESTARI semuanya menumpuk di 1152015 PERSEDIAAN BARANG
	UMUM, padahal kelompok barangnya sudah punya akun sendiri.

	Yang disentuh hanya jurnalnya: kolom account di baris debit GL, plus kolom
	against di baris lawannya supaya laporan tetap terbaca. Stock Ledger Entry,
	valuation rate, dan nilai rupiahnya tidak bergerak sama sekali - debit dan
	kredit tetap sama besar, cuma pindah akun.

	Baris yang TIDAK disentuh:

	    - baris debit yang akunnya bukan akun gudang (aset transit, biaya jasa,
	      asuransi): itu jalur non-stock dan aset, bukan salah tempat
	    - PR yang barang stoknya menunjuk lebih dari satu akun kelompok: satu
	      baris GL gabungan harus dipecah, dan pemecahannya tidak ditebak sendiri
	    - barang yang kelompoknya belum punya akun untuk company itu
	    - PR yang tanggalnya masuk Accounting Period yang sudah disubmit, kecuali
	      dipanggil dengan abaikan_periode=True

	    from sth.patches.koreksi_akun_persediaan_purchase_receipt import execute
	    execute(company="PT. TRIMITRA LESTARI", dari="2026-09-01")
	    execute(company="PT. TRIMITRA LESTARI", dari="2026-09-01", dry_run=False)
	    execute(["MAT-PRE-2026-00084"], dry_run=False)

	Default-nya dry run: mencetak rencana per dokumen, tanpa menulis apa pun.
	"""
	daftar = purchase_receipt or cari_purchase_receipt(company, dari, sampai)

	if not daftar:
		print("Koreksi akun persediaan PR: tidak ada dokumen yang diproses")
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


def cari_purchase_receipt(company=None, dari=None, sampai=None):
	"""Purchase Receipt submit yang masih mendebit akun gudang, bukan akun kelompok."""
	syarat = ["pr.docstatus = 1"]
	nilai = {}

	if company:
		syarat.append("pr.company = %(company)s")
		nilai["company"] = company

	if dari:
		syarat.append("pr.posting_date >= %(dari)s")
		nilai["dari"] = dari

	if sampai:
		syarat.append("pr.posting_date <= %(sampai)s")
		nilai["sampai"] = sampai

	return frappe.db.sql_list(
		"""
		select distinct pr.name
		from `tabPurchase Receipt` pr
		where {}
		order by pr.posting_date, pr.name
		""".format(" and ".join(syarat)),
		nilai,
	)


def _proses_satu(nama, dry_run):
	pr = frappe.db.get_value(
		DOCTYPE, nama, ["name", "company", "posting_date", "docstatus"], as_dict=True
	)

	if not pr:
		return False, "dokumen tidak ada"

	if pr.docstatus != 1:
		return False, f"docstatus {pr.docstatus}, bukan dokumen submit"

	akun_gudang = akun_gudang_purchase_receipt(nama, pr.company)
	if not akun_gudang:
		return False, "tidak punya baris stok"

	baris_gl = frappe.db.sql(
		"""
		select name, account, debit, cost_center
		from `tabGL Entry`
		where voucher_type = %s and voucher_no = %s and is_cancelled = 0 and debit > 0
		""",
		(DOCTYPE, nama),
		as_dict=True,
	)

	salah_tempat = [g for g in baris_gl if g.account in akun_gudang]
	if not salah_tempat:
		return False, "tidak ada baris debit di akun gudang"

	target = akun_target_purchase_receipt(nama, pr.company)

	if target.get("gagal"):
		return False, target["gagal"]

	akun_baru = target["akun"]

	if len(salah_tempat) > 1:
		return False, f"{len(salah_tempat)} baris debit di akun gudang, perlu diperiksa tangan"

	baris = salah_tempat[0]

	if baris.account == akun_baru:
		return False, f"sudah di akun yang benar ({akun_baru})"

	periode = accounting_period_tertutup(pr.posting_date, pr.company)
	if periode:
		return False, f"Accounting Period {periode} sudah disubmit"

	pesan = f"{baris.account} -> {akun_baru} ({frappe.format_value(baris.debit, 'Currency')})"

	if dry_run:
		return True, pesan

	frappe.db.set_value("GL Entry", baris.name, "account", akun_baru, update_modified=False)

	# Kolom against di baris lawan masih menyebut akun lama; ikut ditulis supaya
	# buku besar tidak menunjuk akun yang sudah tidak dipakai dokumen ini.
	frappe.db.sql(
		"""
		update `tabGL Entry`
		set against = %s
		where voucher_type = %s and voucher_no = %s and is_cancelled = 0
		  and name != %s and against = %s
		""",
		(akun_baru, DOCTYPE, nama, baris.name, baris.account),
	)

	return True, pesan


def akun_gudang_purchase_receipt(nama, company):
	"""Akun persediaan bawaan ERPNext untuk dokumen ini: milik gudang, lalu company."""
	gudang = frappe.db.sql_list(
		"""
		select distinct warehouse from `tabStock Ledger Entry`
		where voucher_type = %s and voucher_no = %s and is_cancelled = 0
		""",
		(DOCTYPE, nama),
	)

	if not gudang:
		return set()

	akun = {frappe.db.get_value("Warehouse", w, "account") for w in gudang}
	akun.add(frappe.db.get_value("Company", company, "default_inventory_account"))

	return {a for a in akun if a}


def akun_target_purchase_receipt(nama, company):
	"""Akun kelompok barang untuk seluruh barang stok dokumen ini.

	Urutannya sama dengan yang dipakai saat submit: STH Stock Settings per barang
	dulu, baru akun kelompok barang.
	"""
	item_codes = frappe.db.sql_list(
		"""
		select distinct item_code from `tabStock Ledger Entry`
		where voucher_type = %s and voucher_no = %s and is_cancelled = 0
		""",
		(DOCTYPE, nama),
	)

	akun = set()
	for item_code in item_codes:
		satu = akun_kelompok_barang(item_code, company)

		if not satu:
			return {"gagal": f"barang {item_code} belum punya akun kelompok untuk {company}"}

		akun.add(satu)

	if len(akun) > 1:
		return {"gagal": f"barangnya menunjuk {len(akun)} akun berbeda, perlu dipecah tangan"}

	return {"akun": akun.pop()}


def akun_kelompok_barang(item_code, company):
	khusus = frappe.db.get_value(
		"STH Stock Settings Persediaan Account",
		{"master_barang": item_code, "company": company},
		"account",
	)

	if khusus:
		return khusus

	kelompok = frappe.db.get_value("Item", item_code, "kelompok_barang")
	if not kelompok:
		return None

	return frappe.db.get_value(
		"Account Persediaan Kelompok Barang",
		{"parent": kelompok, "company": company},
		"account",
	)


def accounting_period_tertutup(posting_date, company):
	return frappe.db.get_value(
		"Accounting Period",
		{
			"company": company,
			"docstatus": 1,
			"start_date": ["<=", posting_date],
			"end_date": [">=", posting_date],
		},
		"name",
	)


def _cetak_ringkasan(berhasil, dilewati, dry_run):
	judul = "RENCANA (dry run)" if dry_run else "HASIL"

	print("")
	print(f"=== Koreksi akun persediaan Purchase Receipt - {judul} ===")

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
