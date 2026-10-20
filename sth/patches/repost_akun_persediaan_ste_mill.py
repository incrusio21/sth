import frappe
from frappe.utils import cint, flt

from erpnext.accounts.general_ledger import make_reverse_gl_entries

from sth.accounting_sth.doctype.sth_accounting_settings.sth_accounting_settings import (
	KOLOM_AKUN_PERSEDIAAN,
	get_akun_persediaan,
)
from sth.patches.repost_akun_difference_ste_mill import alasan_periode, lapor_cogs_terdampak, sebab


def execute(terapkan=0, company=None, dari=None, sampai=None, nama=None, cara="langsung"):
	"""Pindahkan akun persediaan Stock Entry lama untuk Item TBS, CPO dan Palm
	Kernel dari akun Kelompok Barang ke akun persediaan di tabel COGS STH
	Accounting Settings, berikut GL-nya.

	Sejak override Stock Entry membaca akun persediaan produk ini dari tabel
	COGS, Stock Entry baru mendarat di sana, sedangkan yang lama tetap di akun
	Kelompok Barang (atau STH Stock Settings). Saldo GL persediaan yang dibaca
	COGS Mill dan Kebun jadi terbelah dua akun.

	Bawaannya cuma melaporkan. Yang mau diubah dijalankan dengan terapkan=1:

	    bench --site <site> execute sth.patches.repost_akun_persediaan_ste_mill.execute
	    bench --site <site> execute sth.patches.repost_akun_persediaan_ste_mill.execute \\
	        --kwargs "{'terapkan': 1, 'dari': '2026-09-01', 'sampai': '2026-09-30'}"

	Penyaringnya: company, dari, sampai (tanggal posting Stock Entry), atau nama
	- nama Stock Entry maupun dokumen sumbernya.

	Akun lamanya tidak tersimpan di baris Stock Entry Detail, jadi dihitung
	ulang dengan aturan lama (STH Stock Settings per item, lalu Kelompok Barang)
	lalu dicocokkan dengan GL Entry hidup Stock Entry itu. GL Stock Entry juga
	tidak menyimpan baris asalnya dan baris dengan akun yang sama sudah
	digabung, jadi penggantiannya per akun per Stock Entry.

	Stock Entry yang periodenya dikunci (Accounting Period, tanggal beku,
	Period Closing Voucher) dilewati dan dilaporkan di kedua cara.

	cara="langsung" (bawaan): akun GL Entry hidup diganti di tempat dengan
	UPDATE. Stock Entry juga dilewati dan dilaporkan kalau akun lama
	juga dipakai barang lain atau sebagai akun expense di Stock Entry yang sama,
	atau kalau dua produk berakun lama sama tapi berakun baru beda.

	cara="balik": GL lama dibalik lalu GL baru disusun ulang dari Stock Ledger
	dengan override yang sudah membaca tabel COGS. Ada jejaknya, tapi lambat
	dan rawan lock wait timeout di produksi.

	Nilainya tidak berubah, cuma akunnya. Akun yang ditemukan sudah sama
	dilewati, jadi aman diulang. Tiap Stock Entry di-commit sendiri.

	Sengaja tidak didaftarkan di patches.txt.
	"""
	terapkan = cint(terapkan)
	if cara not in ("langsung", "balik"):
		frappe.throw("cara harus 'langsung' atau 'balik'.")

	baris = cari_baris(company=company, dari=dari, sampai=sampai, nama=nama)
	if not baris:
		print("Tidak ada Stock Entry submitted berisi Item TBS, CPO atau Palm Kernel yang cocok.")
		return

	akun_tujuan = {}
	belum_diatur = set()
	per_ste = {}

	for row in baris:
		kunci = (row.company, row.tipe_barang)
		if kunci not in akun_tujuan:
			akun_tujuan[kunci] = get_akun_persediaan(row.company, row.tipe_barang)

		row.tujuan = akun_tujuan[kunci]
		if not row.tujuan:
			belum_diatur.add(kunci)
			continue

		row.lama = akun_persediaan_lama(row.company, row.item_code)
		if row.lama == row.tujuan:
			continue

		per_ste.setdefault(row.stock_entry, []).append(row)

	print("{0} baris Stock Entry Detail diperiksa, cara {1}, mode {2}\n".format(
		len(baris), cara.upper(), "TERAPKAN" if terapkan else "LAPORAN SAJA"
	))

	for company_, tipe in sorted(belum_diatur):
		print("Akun persediaan {0} untuk {1} belum diatur di tabel COGS, barisnya dilewati.".format(tipe, company_))
	if belum_diatur:
		print()

	berhasil = []
	dilewati = []
	gagal = []
	tanpa_gl = 0

	for nama_ste, rows in per_ste.items():
		pertama = rows[0]
		gl_lama = akun_gl_hidup(nama_ste)

		# Akun lama yang tidak ada di GL: barisnya tidak berjurnal (nilai nol)
		# atau sudah dipindah lewat jalan lain.
		if not any(row.lama in gl_lama for row in rows):
			tanpa_gl += 1
			continue

		print("{0}  {1}  {2} {3}".format(
			nama_ste, pertama.posting_date, pertama.reference_doctype or "-", pertama.references or ""
		))
		for row in rows:
			print("    {0:<16} {1:>16}  {2} -> {3}".format(
				row.item_code, flt(row.amount, 2), row.lama or "-", row.tujuan
			))

		# Penjaga periode diperiksa di kedua cara: make_gl_entries tidak
		# menolak posting ulang ke periode yang ditutup Accounting Period.
		alasan = alasan_periode(pertama.company, pertama.posting_date)
		if not alasan and cara == "langsung":
			alasan = alasan_dilewati(nama_ste, rows)
		if alasan:
			dilewati.append((nama_ste, alasan))
			print("    DILEWATI — {0}".format(alasan))
			continue

		if not terapkan:
			continue

		titik = "repost_akun_persediaan_ste"
		try:
			frappe.db.savepoint(titik)
			if cara == "langsung":
				jumlah_gl = ganti_langsung(nama_ste, rows)
				keterangan = "diganti langsung, {0} baris GL".format(jumlah_gl)
			else:
				posting_ulang(nama_ste)
				keterangan = "diposting ulang"
			frappe.db.commit()
			berhasil.append(pertama)
			print("    {0}".format(keterangan))
		except Exception as e:
			if frappe.message_log:
				frappe.message_log.pop()

			frappe.db.rollback(save_point=titik)
			pesan = sebab(e)
			gagal.append((nama_ste, pesan))
			print("    GAGAL — {0}".format(pesan))

	jumlah = len(per_ste) - tanpa_gl
	print("\nStock Entry dengan akun berbeda : {0}".format(jumlah))
	print("tanpa GL akun lama (dilewati)   : {0}".format(tanpa_gl))
	print("dilewati                        : {0}".format(len(dilewati)))
	if terapkan:
		print("diubah                          : {0}".format(len(berhasil)))
		print("gagal                           : {0}".format(len(gagal)))

	for nama_ste, pesan in gagal:
		print("  {0}: {1}".format(nama_ste, pesan[:200]))

	if not terapkan and jumlah > len(dilewati):
		print(
			"\nBelum ada yang disentuh. Ulangi dengan terapkan=1 untuk mengubah "
			"Stock Entry di atas yang tidak dilewati."
		)

	if terapkan:
		terdampak = berhasil
	else:
		lewat = {n for n, _ in dilewati}
		terdampak = [
			rows[0] for n, rows in per_ste.items()
			if n not in lewat and any(r.lama in akun_gl_hidup(n) for r in rows)
		]
	if terdampak:
		lapor_cogs_terdampak(terdampak)


def cari_baris(company=None, dari=None, sampai=None, nama=None):
	"""Baris Stock Entry Detail submitted yang barangnya bertipe TBS, CPO atau
	Palm Kernel, dari Stock Entry apa pun."""
	syarat = ["se.docstatus = 1", "i.tipe_barang in %(tipe)s"]
	params = {"tipe": tuple(KOLOM_AKUN_PERSEDIAAN)}

	if nama:
		syarat.append("(se.name = %(nama)s or se.references = %(nama)s)")
		params["nama"] = nama
	if company:
		syarat.append("se.company = %(company)s")
		params["company"] = company
	if dari:
		syarat.append("se.posting_date >= %(dari)s")
		params["dari"] = dari
	if sampai:
		syarat.append("se.posting_date <= %(sampai)s")
		params["sampai"] = sampai

	return frappe.db.sql("""
		select se.name as stock_entry, se.company, se.posting_date,
			se.reference_doctype, se.references,
			sed.name as detail, sed.item_code, sed.expense_account, sed.amount,
			i.tipe_barang
		from `tabStock Entry Detail` sed
		inner join `tabStock Entry` se on se.name = sed.parent
		inner join `tabItem` i on i.name = sed.item_code
		where {syarat}
		order by se.posting_date, se.name, sed.idx
	""".format(syarat=" and ".join(syarat)), params, as_dict=True)


def akun_persediaan_lama(company, item_code):
	"""Akun persediaan menurut aturan override Stock Entry sebelum tabel COGS
	dipakai: STH Stock Settings per item, lalu Kelompok Barang item itu."""
	akun = frappe.db.get_value(
		"STH Stock Settings Persediaan Account",
		{"parent": "STH Stock Settings", "master_barang": item_code, "company": company},
		"account",
	)
	if akun:
		return akun

	kelompok = frappe.get_cached_value("Item", item_code, "kelompok_barang")
	if not kelompok:
		return None
	return frappe.db.get_value(
		"Account Persediaan Kelompok Barang",
		{"parent": kelompok, "parenttype": "Item Group", "company": company},
		"account",
	)


def akun_gl_hidup(nama_ste):
	return set(frappe.get_all(
		"GL Entry",
		filters={"voucher_type": "Stock Entry", "voucher_no": nama_ste, "is_cancelled": 0},
		pluck="account",
		distinct=True,
	))


def alasan_dilewati(nama_ste, rows):
	"""Kenapa akun GL Stock Entry ini tidak bisa diganti langsung, atau None.
	Penjaga periodenya diperiksa terpisah lewat alasan_periode."""
	pertama = rows[0]
	peta = {}
	for row in rows:
		if not row.lama:
			return "akun lama {0} tidak bisa ditentukan, pakai cara='balik'".format(row.item_code)
		if peta.setdefault(row.lama, row.tujuan) != row.tujuan:
			return "{0} dipakai dua produk dengan akun baru berbeda, pakai cara='balik'".format(row.lama)

		mata_uang_lama = frappe.db.get_value("Account", row.lama, "account_currency")
		mata_uang_baru = frappe.db.get_value("Account", row.tujuan, "account_currency")
		if mata_uang_lama != mata_uang_baru:
			return "mata uang {0} dan {1} berbeda".format(row.lama, row.tujuan)

	# GL Stock Entry digabung per akun, jadi akun lama yang juga dipakai baris
	# lain - barang non produk atau akun expense - tidak bisa dipisahkan.
	produk = {row.detail for row in rows}
	for lain in frappe.get_all(
		"Stock Entry Detail",
		filters={"parent": nama_ste, "parenttype": "Stock Entry"},
		fields=["name", "item_code", "expense_account"],
	):
		if lain.expense_account in peta:
			return "{0} juga akun expense baris {1}, pakai cara='balik'".format(
				lain.expense_account, lain.item_code
			)
		if lain.name not in produk and akun_persediaan_lama(pertama.company, lain.item_code) in peta:
			return "baris {0} juga berakun persediaan lama yang sama, pakai cara='balik'".format(
				lain.item_code
			)


def ganti_langsung(nama_ste, rows):
	"""Ganti akun GL Entry hidup Stock Entry ini dari akun lama ke akun tabel
	COGS, termasuk kolom against. Memulangkan jumlah baris GL yang diganti."""
	pasangan = {(row.lama, row.tujuan) for row in rows}

	jumlah = 0
	for lama, baru in pasangan:
		nilai = {"voucher_no": nama_ste, "lama": lama, "baru": baru}
		jumlah += frappe.db.sql("""
			select count(*) from `tabGL Entry`
			where voucher_type = 'Stock Entry' and voucher_no = %(voucher_no)s
				and is_cancelled = 0 and account = %(lama)s
		""", nilai)[0][0]

		frappe.db.sql("""
			update `tabGL Entry` set account = %(baru)s
			where voucher_type = 'Stock Entry' and voucher_no = %(voucher_no)s
				and is_cancelled = 0 and account = %(lama)s
		""", nilai)
		frappe.db.sql("""
			update `tabGL Entry` set against = %(baru)s
			where voucher_type = 'Stock Entry' and voucher_no = %(voucher_no)s
				and is_cancelled = 0 and against = %(lama)s
		""", nilai)

	return jumlah


def posting_ulang(nama_ste):
	"""Balik GL lama lalu posting GL baru lewat override yang sudah membaca
	akun persediaan dari tabel COGS."""
	make_reverse_gl_entries(voucher_type="Stock Entry", voucher_no=nama_ste)

	doc = frappe.get_doc("Stock Entry", nama_ste)
	doc.make_gl_entries()
