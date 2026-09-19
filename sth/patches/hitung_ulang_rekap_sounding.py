import frappe

from sth.mill.rekap_sounding import REKAP_SOUNDING, hitung_ulang_rekap

# Sejak 2 September. Dokumen sebelumnya dibiarkan apa adanya beserta Stock
# Entry-nya, jadi periode yang sudah dilaporkan tidak ikut bergerak. Stock awal
# dokumen pertama di rentang ini dibaca dari saldo Stock Ledger seperti biasa,
# jadi tidak ada angka semaian yang perlu ditetapkan dan rantai sebelumnya tidak
# ikut tersentuh.
#
# Hari pertama rentang selalu ikut menanggung kesalahan tanggal Stock Entry
# dokumen sebelum rentang, dan di sini memang ada: seluruh sounding 25 Agustus
# sampai 1 September Stock Entry-nya bertanggal mundur sehari — sisa dari
# sebelum set_posting_time dipasang. SSCPODB-0062 (1 September) karena itu
# memposting ke 2 September, sehingga stock awal 3 September kelebihan 79.177,59
# dan produksi dua hari itu terbelah salah: 2 September jadi OER 39,69% dan 3
# September 0,18%, walau gabungannya 17,95% dan 4 September ke atas benar semua.
#
# Menggeser SEJAK ke 1 September cuma memindahkan belahannya ke 1-2 September,
# bukan menghilangkannya, karena tanggal STE 31 Agustus juga masih salah.
# Membereskannya berarti mundur sampai ke pangkal rantai itu — pekerjaan
# tersendiri, karena Agustus memuat angka yang jelas rusak (SSCPODB-0056
# produksi -7.302.367) dan periodenya kemungkinan sudah ditutup.
SEJAK = "2026-09-02"


def execute(sejak=SEJAK, doctype=None, unit=None, posting_ulang=True):
	"""Baca ulang rekap sounding CPO dan Palm Kernel sejak SEJAK, berikut Stock Entry-nya.

	Rekapnya — stock awal, adjustment, pengiriman, stock akhir, produksi,
	rendemen harian, dan rekap bulanannya — cuma ditulis waktu tombol Get Data
	ditekan. Pengiriman CPO yang masuk sesudah soundingnya disubmit tidak pernah
	terbaca lagi, dan dokumen yang sudah disubmit tidak akan menyusul sendiri.
	Sejak sekarang Timbangan CPO/PK mengantrikan hitung ulang sendiri, tapi
	dokumen yang telanjur tertinggal sebelum itu perlu dikejar sekali ini.

	Tiap unit dikerjakan terpisah dan berurutan menurut tanggal proses: stock
	awal sebuah dokumen dibentuk Stock Entry produksi dokumen sebelumnya, jadi
	dokumen tidak bisa dibetulkan satu-satu.

	`posting_ulang=False` bukan mode "angka saja" yang aman, beda dengan patch
	Data TBS yang memang dua fase. Stock awal sounding dibaca dari Stock Ledger,
	jadi selama Stock Entry lama belum diganti, tiap hari berikutnya membaca
	saldo yang masih memuat produksi versi lama — dan selisih yang sama dihitung
	ulang sebagai produksi di setiap hari. Diuji di kloning 19 September: selisih
	210.000 kg dari tiga pengiriman yang telat masuk terbaca berulang sampai OER
	harian tembus 77%, padahal dengan Stock Entry ikut diposting ulang angkanya
	mendarat di 18-19%.

	Jadi pakai `posting_ulang=False` cuma untuk melihat-lihat di kloning, jangan
	untuk membetulkan data. Kalau pembatalan Stock Entry tertahan periode
	akuntansi yang sudah tutup, yang dibuka periodenya — bukan fase STE-nya yang
	dilewati.

	Aman dijalankan ulang: dokumen yang angkanya sudah cocok dan Stock Entry
	yang sudah sesuai sama-sama dilewati. Tiap dokumen di-commit begitu selesai,
	jadi kalau ada yang gagal, dokumen yang sudah beres tidak ikut hangus.

	    bench --site <site> execute sth.patches.hitung_ulang_rekap_sounding.execute

	Satu doctype atau satu unit saja:

	    bench --site <site> execute sth.patches.hitung_ulang_rekap_sounding.execute \
	        --kwargs "{'doctype': 'Sounding Stock CPO di BST', 'unit': 'TPRM'}"
	"""
	doctypes = [doctype] if doctype else list(REKAP_SOUNDING)
	total = frappe._dict(dokumen=0, angka=0, ste=0)

	for nama in doctypes:
		for unit_ini in unit_dikerjakan(nama, sejak, unit):
			print("== {0} unit {1} sejak {2}".format(nama, unit_ini, sejak))

			hasil = hitung_ulang_rekap(
				nama, unit_ini, sejak, posting_ulang=posting_ulang, lapor=print
			)

			print("   {0} dokumen, {1} angka berubah, {2} Stock Entry dibuat ulang.".format(
				hasil.dokumen, hasil.angka, hasil.ste))

			for kunci in total:
				total[kunci] += hasil[kunci]

	print("Total: {0} dokumen ditelusuri, {1} angkanya berubah, {2} Stock Entry dibuat ulang.".format(
		total.dokumen, total.angka, total.ste))

	laporkan_antrian_repost()


def unit_dikerjakan(doctype, sejak, unit=None):
	"""Unit yang punya dokumen sounding sejak tanggal itu.

	Diambil dari dokumennya sendiri, bukan dari master Unit: unit yang tidak
	pernah membuat sounding di rentang ini tidak perlu dilewati sama sekali.
	"""
	if unit:
		return [unit]

	return [
		nama
		for nama in frappe.get_all(
			doctype,
			filters={"docstatus": ("<", 2), "tanggal_proses": (">=", sejak)},
			pluck="unit",
			distinct=True,
			order_by="unit asc",
			limit_page_length=0,
		)
		if nama
	]


def laporkan_antrian_repost():
	"""Penilaian stok dihitung ulang scheduler, bukan patch ini.

	Stock Entry bertanggal mundur bikin ERPNext mengantrikan Repost Item
	Valuation. Menjalankannya di sini bisa memakan waktu berjam-jam dan menahan
	pemanggilnya.
	"""
	antri = frappe.db.count("Repost Item Valuation", {"status": ("in", ("Queued", "In Progress"))})

	if antri:
		print("{0} Repost Item Valuation mengantre, nilai stok menyesuaikan setelah scheduler selesai.".format(antri))
