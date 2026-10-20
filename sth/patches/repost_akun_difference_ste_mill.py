import frappe
from frappe.utils import cint, flt, getdate

from erpnext.accounts.general_ledger import make_reverse_gl_entries

from sth.accounting_sth.doctype.sth_accounting_settings.sth_accounting_settings import get_akun_difference

# Dokumen sumber Stock Entry produksi mill dan tipe barang yang akun
# difference-nya dibaca dari STH Accounting Settings.
SUMBER = {
	"Data TBS": "TBS",
	"Sounding Stock CPO di BST": "CPO",
	"Sounding Stock Palm Kernel di Bunker Kernel": "Palm Kernel",
}


def execute(terapkan=0, company=None, dari=None, sampai=None, nama=None, cara="langsung"):
	"""Ganti akun difference Stock Entry Data TBS / Sounding CPO / Sounding PK
	yang sudah disubmit ke akun di STH Accounting Settings, berikut GL-nya.

	Stock Entry yang dibuat sebelum tabel Akun Difference Produksi Mill diisi
	memakai akun bawaan ERPNext (Item Default lalu Stock Adjustment Account
	company), dan setelan baru tidak menjalar ke dokumen lama. Akibatnya satu
	periode bisa memegang dua akun lawan sekaligus, yang ditolak jurnal COGS
	Mill dan Kebun.

	Bawaannya cuma melaporkan. Yang mau diubah dijalankan dengan terapkan=1:

	    bench --site <site> execute sth.patches.repost_akun_difference_ste_mill.execute
	    bench --site <site> execute sth.patches.repost_akun_difference_ste_mill.execute \\
	        --kwargs "{'terapkan': 1, 'dari': '2026-09-01', 'sampai': '2026-09-30'}"

	Penyaringnya: company, dari, sampai (tanggal posting Stock Entry), atau nama
	- nama Stock Entry maupun dokumen sumbernya. Sebaiknya per bulan penuh,
	supaya COGS bulan itu tidak tertinggal dengan akun lawan campuran.

	Baris Stock Entry Detail yang akunnya sudah sama dilewati, jadi patch ini
	aman diulang. Tipe barang yang akunnya belum diatur untuk company itu juga
	dilewati - tidak ada tujuan untuk dipindahkan.

	cara="langsung" (bawaan): expense_account baris dan akun GL Entry-nya yang
	masih hidup diganti di tempat dengan UPDATE. Cepat dan tidak membuat GL
	baru, tapi tidak meninggalkan jejak dan melewati penjaga ERPNext, jadi
	penjaganya diperiksa sendiri lebih dulu: Accounting Period yang menutup
	Stock Entry, tanggal beku akun, dan Period Closing Voucher (saldo Account
	Closing Balance-nya tidak ikut berubah). Stock Entry yang kena salah satunya,
	atau yang punya baris lain dengan akun lama yang sama, dilewati dan
	dilaporkan.

	cara="balik": GL lama dibalik dengan tanggal posting yang sama lalu GL baru
	disusun dari Stock Ledger. Ada jejaknya dan penjaga ERPNext berlaku sendiri,
	tapi lambat dan rawan lock wait timeout di produksi yang sedang ramai.

	Nilainya tidak berubah di kedua cara, cuma akun lawannya; Repost Item
	Valuation sesudahnya juga memakai akun baru karena membaca dari baris yang
	sama. Tiap Stock Entry di-commit sendiri begitu selesai, jadi kalau patch
	berhenti di tengah cukup dijalankan ulang.

	Sengaja tidak didaftarkan di patches.txt: mengubah jurnal persediaan bukan
	sesuatu yang boleh jalan sendiri tiap migrate.
	"""
	terapkan = cint(terapkan)
	if cara not in ("langsung", "balik"):
		frappe.throw("cara harus 'langsung' atau 'balik'.")

	baris = cari_baris(company=company, dari=dari, sampai=sampai, nama=nama)

	if not baris:
		print("Tidak ada Stock Entry produksi mill submitted yang cocok dengan penyaringnya.")
		return

	akun_tujuan = {}
	belum_diatur = set()
	per_ste = {}

	for row in baris:
		kunci = (row.company, row.tipe)
		if kunci not in akun_tujuan:
			akun_tujuan[kunci] = get_akun_difference(row.company, row.tipe)

		tujuan = akun_tujuan[kunci]
		if not tujuan:
			belum_diatur.add(kunci)
			continue
		if row.expense_account == tujuan:
			continue

		row.tujuan = tujuan
		per_ste.setdefault(row.stock_entry, []).append(row)

	print("{0} baris Stock Entry Detail diperiksa, cara {1}, mode {2}\n".format(
		len(baris), cara.upper(), "TERAPKAN" if terapkan else "LAPORAN SAJA"
	))

	for company_, tipe in sorted(belum_diatur):
		print("Akun difference {0} untuk {1} belum diatur, barisnya dilewati.".format(tipe, company_))
	if belum_diatur:
		print()

	berhasil = []
	dilewati = []
	gagal = []

	for nama_ste, rows in per_ste.items():
		pertama = rows[0]
		print("{0}  {1}  {2} {3}".format(
			nama_ste, pertama.posting_date, pertama.reference_doctype, pertama.references
		))
		for row in rows:
			print("    {0:<16} {1:>16}  {2} -> {3}".format(
				row.item_code, flt(row.amount, 2), row.expense_account or "-", row.tujuan
			))

		if cara == "langsung":
			alasan = alasan_dilewati(nama_ste, rows)
			if alasan:
				dilewati.append((nama_ste, alasan))
				print("    DILEWATI — {0}".format(alasan))
				continue

		if not terapkan:
			continue

		# Di-commit per Stock Entry. Satu transaksi untuk semuanya menahan kunci
		# sampai patch selesai, sehingga pengguna lain dan patch ini saling
		# menunggu sampai lock wait timeout.
		titik = "repost_akun_difference_ste"
		try:
			frappe.db.savepoint(titik)
			if cara == "langsung":
				jumlah_gl = ganti_langsung(nama_ste, rows)
				keterangan = "diganti langsung, {0} baris GL".format(jumlah_gl)
			else:
				posting_ulang(nama_ste, rows)
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

	print("\nStock Entry dengan akun berbeda : {0}".format(len(per_ste)))
	print("dilewati                        : {0}".format(len(dilewati)))
	if terapkan:
		print("diubah                          : {0}".format(len(berhasil)))
		print("gagal                           : {0}".format(len(gagal)))

	for nama_ste, pesan in gagal:
		print("  {0}: {1}".format(nama_ste, pesan[:200]))

	if not terapkan and len(per_ste) > len(dilewati):
		print(
			"\nBelum ada yang disentuh. Ulangi dengan terapkan=1 untuk mengubah "
			"Stock Entry di atas yang tidak dilewati."
		)

	# Jurnal kapitalisasi COGS yang sudah disubmit mendebit akun lawan lama;
	# sesudah Stock Entry-nya pindah akun, akun lama itu tidak nol lagi.
	if terapkan:
		terdampak = berhasil
	else:
		lewat = {n for n, _ in dilewati}
		terdampak = [rows[0] for n, rows in per_ste.items() if n not in lewat]
	if terdampak:
		lapor_cogs_terdampak(terdampak)


def cari_baris(company=None, dari=None, sampai=None, nama=None):
	"""Baris Stock Entry Detail submitted bikinan dokumen sumber produksi mill,
	masuk maupun keluar, yang barangnya sesuai tipe dokumen sumbernya."""
	syarat = [
		"se.docstatus = 1",
		"se.reference_doctype in %(doctypes)s",
		"ifnull(se.references, '') != ''",
	]
	params = {"doctypes": tuple(SUMBER)}

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

	rows = frappe.db.sql("""
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

	hasil = []
	for row in rows:
		row.tipe = SUMBER[row.reference_doctype]
		if row.tipe_barang == row.tipe:
			hasil.append(row)

	return hasil


def alasan_dilewati(nama_ste, rows):
	"""Kenapa Stock Entry ini tidak boleh diganti langsung, atau None.

	UPDATE langsung melewati penjaga yang biasanya diperiksa make_gl_entries,
	jadi diperiksa di sini dengan aturan yang sama - tanpa pengecualian peran
	untuk tanggal beku, karena patch ini tidak dijalankan atas nama siapa pun.
	"""
	pertama = rows[0]

	periode = frappe.db.sql("""
		select ap.name
		from `tabAccounting Period` ap
		inner join `tabClosed Document` cd on cd.parent = ap.name
		where ap.company = %(company)s and cd.closed = 1
			and cd.document_type = 'Stock Entry'
			and %(tanggal)s between ap.start_date and ap.end_date
		limit 1
	""", {"company": pertama.company, "tanggal": pertama.posting_date})
	if periode:
		return "periode ditutup Accounting Period {0}".format(periode[0][0])

	beku = frappe.db.get_single_value("Accounts Settings", "acc_frozen_upto")
	if beku and getdate(pertama.posting_date) <= getdate(beku):
		return "akun dibekukan sampai {0}".format(beku)

	pcv = frappe.db.get_value(
		"Period Closing Voucher",
		{"docstatus": 1, "company": pertama.company, "period_end_date": (">=", pertama.posting_date)},
		"name",
	)
	if pcv:
		return "sudah ada Period Closing Voucher {0}".format(pcv)

	detail = tuple(row.detail for row in rows)
	for row in rows:
		if not row.expense_account:
			return "baris {0} tidak punya akun lama, pakai cara='balik'".format(row.item_code)

		mata_uang_lama = frappe.db.get_value("Account", row.expense_account, "account_currency")
		mata_uang_baru = frappe.db.get_value("Account", row.tujuan, "account_currency")
		if mata_uang_lama != mata_uang_baru:
			return "mata uang {0} dan {1} berbeda".format(row.expense_account, row.tujuan)

		lain = frappe.db.sql("""
			select item_code from `tabStock Entry Detail`
			where parent = %s and expense_account = %s and name not in %s
			limit 1
		""", (nama_ste, row.expense_account, detail))
		if lain:
			return "baris {0} juga memakai {1}, GL-nya tidak bisa dipisah".format(
				lain[0][0], row.expense_account
			)


def ganti_langsung(nama_ste, rows):
	"""Ganti akun di Stock Entry Detail dan GL Entry hidup milik Stock Entry ini.

	Baris GL persediaan menyimpan akun lawannya di kolom against, jadi ikut
	diganti. Memulangkan jumlah baris GL yang akunnya diganti.
	"""
	pasangan = set()
	for row in rows:
		frappe.db.set_value(
			"Stock Entry Detail", row.detail, "expense_account", row.tujuan, update_modified=False
		)
		pasangan.add((row.expense_account, row.tujuan))

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


def posting_ulang(nama_ste, rows):
	"""Tulis akun barunya ke baris, balik GL lama, lalu posting GL baru.

	Dibalik, bukan dihapus, supaya jejaknya tetap ada dan penjaga periode
	tertutup serta tanggal beku tetap berlaku - keduanya ikut diperiksa
	make_reverse_gl_entries dan make_gl_entries.
	"""
	for row in rows:
		frappe.db.set_value(
			"Stock Entry Detail", row.detail, "expense_account", row.tujuan, update_modified=False
		)

	make_reverse_gl_entries(voucher_type="Stock Entry", voucher_no=nama_ste)

	doc = frappe.get_doc("Stock Entry", nama_ste)
	doc.make_gl_entries()


def sebab(e):
	"""Pesan penolakan yang terbaca, tanpa markup frappe.throw."""
	return frappe.utils.strip_html(str(e)).strip() or e.__class__.__name__


def lapor_cogs_terdampak(rows):
	"""COGS Mill dan Kebun submitted yang periodenya memuat Stock Entry yang
	akunnya berubah."""
	if not frappe.db.table_exists("COGS Mill dan Kebun"):
		return

	terdampak = {}
	for row in rows:
		for d in frappe.get_all(
			"COGS Mill dan Kebun",
			filters={
				"docstatus": 1,
				"company": row.company,
				"periode_dari": ("<=", row.posting_date),
				"periode_sampai": (">=", row.posting_date),
			},
			fields=["name", "company", "unit", "periode_dari", "periode_sampai"],
			limit_page_length=0,
		):
			terdampak[d.name] = d

	if not terdampak:
		print("\nTidak ada COGS Mill dan Kebun submitted di periode yang berubah.")
		return

	print(
		"\nCOGS Mill dan Kebun submitted di periode yang berubah - jurnal "
		"kapitalisasinya masih mendebit akun lawan lama, perlu dibatalkan lalu "
		"disubmit ulang (dari bulan paling akhir):"
	)
	for d in sorted(terdampak.values(), key=lambda d: d.periode_dari, reverse=True):
		print("  {0:<24} {1} {2} {3} s/d {4}".format(
			d.name, d.company, d.unit or "-", d.periode_dari, d.periode_sampai
		))
