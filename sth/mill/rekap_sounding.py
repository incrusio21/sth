"""Hitung ulang rekap dua doctype sounding, dan pemicunya dari Timbangan.

Dipisah dari mill/utils.py yang isinya potongan-potongan kecil: yang di sini
satu alur kerja utuh yang dipakai tiga jalan masuk sekaligus — tombol Hitung
Ulang di form, background job sesudah Timbangan, dan patch data lama.
"""

import contextlib

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate

from sth.mill.utils import (
	buat_ulang_ste,
	izinkan_stock_minus,
	set_rata_rata_rendemen_bulanan,
)

# Nama field dan method beda antara CPO dan Palm Kernel, sementara urutan
# kerjanya persis sama. Alasannya sama dengan RENDEMEN_BULANAN di mill/utils.py:
# yang dibedakan cuma tabel ini, bukan dua salinan fungsi yang gampang
# ketinggalan sebelah.
REKAP_SOUNDING = {
	"Sounding Stock CPO di BST": {
		"tipe_barang": "CPO",
		# Method yang membaca ulang seluruh rekap dari sumbernya. Ini juga yang
		# dijalankan tombol Get Data di form, jadi hasil hitung ulang di sini
		# tidak pernah beda dengan hasil orang menekan tombol itu sendiri.
		"baca_ulang": "get_data",
		"produksi": "produksi_cpo",
		# create_ste-nya menjaga sendiri: produksi nol dilewati, minus keluar
		# sebagai Material Issue.
		"ste_hanya_positif": False,
		"turunan": (
			"stock_awal_sebelum_adjustment", "adjustment", "stock_awal",
			"pengiriman_cpo", "stock_bst", "produksi_cpo",
			"tbs_olah", "potongan_sortasi", "oer_netto_1", "oer_netto_2",
			"total_produksi_bulanan", "rata_rata_oer_bulanan",
		),
	},
	"Sounding Stock Palm Kernel di Bunker Kernel": {
		"tipe_barang": "Palm Kernel",
		"baca_ulang": "get_stock",
		"produksi": "produksi",
		# Produksi nol atau minus tidak pernah jadi Stock Entry di Palm Kernel,
		# beda dengan CPO. Penjaganya di create_ste-nya sendiri; dicatat lagi di
		# sini supaya pengecekan "STE sudah benar" ikut tahu.
		"ste_hanya_positif": True,
		"turunan": (
			"stock_awal_sebelum_adjustment", "adjustment", "stock_awal",
			"pengiriman", "stock_akhir", "produksi",
			"tbs_olah", "sortasi", "ker_netto_1", "ker_netto_2",
			"total_produksi_bulanan", "rata_rata_ker_bulanan",
		),
	},
}


def hitung_ulang_rekap(
	doctype, unit, sejak, posting_ulang=True, izinkan_minus=True, commit=True, lapor=None
):
	"""Baca ulang rekap sounding satu unit sejak satu tanggal, berikut Stock Entry-nya.

	Seluruh rekap — stock awal, adjustment, pengiriman, stock akhir, produksi,
	rendemen harian, dan rekap bulanannya — cuma ditulis waktu tombol Get Data
	ditekan. Apa pun yang berubah sesudah itu tidak pernah terbaca lagi:
	pengiriman yang masuk belakangan, timbangan bertanggal mundur, koreksi stok,
	maupun Data TBS yang tbs olahnya baru dibetulkan. Dokumen yang sudah
	disubmit tidak akan menyusul sendiri.

	Hari-hari sesudahnya ikut dihitung karena rantainya lewat Stock Ledger:
	stock awal sebuah dokumen adalah saldo gudang di sekitar tanggal prosesnya,
	dan saldo itu dibentuk Stock Entry produksi dokumen-dokumen sebelumnya.

	Karena itu dokumennya tidak diproses dua fase seperti Data TBS, melainkan
	satu lingkaran berurutan: angka satu dokumen dibetulkan, Stock Entry-nya
	langsung diposting ulang, baru dokumen berikutnya membaca saldo. Kalau
	fasenya dipisah, dokumen kedua dan seterusnya akan membaca saldo yang masih
	dibentuk Stock Entry lama.

	Rekap bulanannya ikut benar lewat urutan yang sama:
	set_rata_rata_rendemen_bulanan menjumlahkan dokumen submitted sejak awal
	bulan sampai tanggal dokumen ini saja, jadi yang dibacanya selalu dokumen
	yang sudah dilewati lingkaran ini.

	Lingkaran yang sama itu juga alasan `posting_ulang=False` tidak bisa dipakai
	untuk membetulkan data. Tanpa Stock Entry ikut diganti, saldo yang dibaca
	hari berikutnya masih dibentuk produksi versi lama, jadi selisih yang sama
	dihitung ulang sebagai produksi di setiap hari sesudahnya. Di kloning 19
	September selisih 210.000 kg terbaca berulang sampai OER harian tembus 77%.
	Simpan untuk melihat-lihat saja.

	`izinkan_minus` mematikan sementara larangan stok minus selama Stock Entry
	lama dibatalkan. Wajib mati waktu dipanggil dari dalam transaksi submit
	orang lain: penjaganya me-rollback pekerjaan yang belum di-commit waktu
	selesai, dan itu akan ikut membuang submit yang sedang berjalan.

	Aman dijalankan ulang: dokumen yang angkanya sudah cocok dan Stock Entry
	yang sudah sesuai sama-sama dilewati. Dari konsol:

	    bench --site NAMA execute sth.mill.rekap_sounding.hitung_ulang_rekap
	        --kwargs "{'doctype': 'Sounding Stock CPO di BST', 'unit': 'TPRM', 'sejak': '2026-09-02'}"
	"""
	cfg = REKAP_SOUNDING[doctype]
	lapor = lapor or (lambda pesan: None)
	sejak = getdate(sejak)

	dokumen = frappe.get_all(
		doctype,
		filters={"unit": unit, "docstatus": ("<", 2), "tanggal_proses": (">=", sejak)},
		fields=["name"],
		order_by="tanggal_proses asc, creation asc",
		limit_page_length=0,
	)

	hasil = frappe._dict(dokumen=len(dokumen), angka=0, ste=0)

	if not dokumen:
		return hasil

	penjaga = izinkan_stock_minus() if izinkan_minus else contextlib.nullcontext()

	with penjaga:
		for urutan, row in enumerate(dokumen, 1):
			doc = frappe.get_doc(doctype, row.name)
			sebelum = angka_rekap(doc, cfg)

			doc.run_method(cfg["baca_ulang"])

			# Ditulis dua kali, dan urutannya bukan kebetulan.
			# set_rata_rata_rendemen_bulanan menjumlahkan dokumen submitted
			# lewat SQL — termasuk dokumen ini sendiri — jadi produksi hari ini
			# harus sudah mendarat di tabelnya sebelum rekap bulanan dihitung.
			# Kalau dibalik, rekap bulanannya memakai produksi versi lama dan
			# dokumen terakhir tiap bulan selalu tertinggal satu hari.
			#
			# db_update, bukan save: sebagian dokumennya sudah disubmit, dan
			# yang berubah cuma angka turunan yang read only di form.
			doc.db_update()
			set_rata_rata_rendemen_bulanan(doc)
			doc.db_update()

			if angka_rekap(doc, cfg) != sebelum:
				hasil.angka += 1

			# Draft belum punya Stock Entry dan tidak boleh dibuatkan di sini:
			# yang membuatnya on_submit, nanti waktu dokumennya benar-benar
			# disubmit.
			if posting_ulang and doc.docstatus == 1 and not ste_sudah_benar(doc, cfg):
				hasil.ste += buat_ulang_ste(doc)

			if commit:
				frappe.db.commit()

			lapor("[{0}/{1}] {2} selesai.".format(urutan, len(dokumen), doc.name))

	# Dicatat juga waktu dipanggil dari background job, yang tidak punya tempat
	# lain untuk melapor: log jobnya cuma menyimpan sukses atau gagal.
	frappe.logger("sounding").info(
		"hitung_ulang_rekap {0} {1} sejak {2}: {3} dokumen, {4} angka berubah, {5} Stock Entry dibuat ulang".format(
			doctype, unit, sejak, hasil.dokumen, hasil.angka, hasil.ste))

	return hasil


def angka_rekap(doc, cfg):
	"""Angka rekap dokumen, dibulatkan supaya bisa dibanding.

	Presisi field tidak dipakai: sebagian field stok presisinya 0 supaya tampil
	bulat di form, padahal selisih setengah kilo tetap harus ikut dibetulkan.
	Nilai yang dibaca dari kolom decimal juga selalu beda di digit terakhir dari
	hasil hitungan float, jadi tanpa pembulatan tidak ada dokumen yang pernah
	dianggap sudah cocok.
	"""
	return tuple(flt(doc.get(field), 3) for field in cfg["turunan"])


def ste_sudah_benar(doc, cfg):
	"""Benar kalau tanggal, arah, dan qty Stock Entry-nya cocok dengan produksinya.

	Dipakai supaya dokumen yang produksinya tidak bergeser tidak ikut dibatalkan
	dan dibuat ulang — pembatalan Stock Entry mengantrikan Repost Item Valuation
	dan tidak gratis.
	"""
	produksi = flt(doc.get(cfg["produksi"]))

	ste = frappe.get_all(
		"Stock Entry",
		filters={"references": doc.name, "docstatus": 1},
		fields=["name", "posting_date", "stock_entry_type"],
	)

	# Syaratnya sengaja disamakan dengan create_ste masing-masing controller:
	# CPO melewati produksi nol, Palm Kernel melewati nol dan minus sekaligus.
	perlu_ste = produksi > 0 if cfg["ste_hanya_positif"] else bool(round(produksi, 2))

	if not perlu_ste:
		return not ste

	if len(ste) != 1:
		return False

	ste = ste[0]

	if getdate(ste.posting_date) != getdate(doc.tanggal_proses):
		return False

	if ste.stock_entry_type != ("Material Receipt" if produksi > 0 else "Material Issue"):
		return False

	qty = frappe.db.get_value("Stock Entry Detail", {"parent": ste.name}, "sum(qty)")

	# Toleransi sekilo per seratus, di bawah presisi qty Stock Entry, supaya STE
	# yang cuma beda pembulatan tidak ikut diposting ulang.
	return abs(flt(qty) - abs(produksi)) < 0.01


def hitung_ulang_setelah_timbangan(doc, method=None):
	"""Antrikan hitung ulang rekap sounding sesudah Timbangan CPO/PK disubmit atau dibatalkan.

	Pengiriman CPO maupun Palm Kernel dibaca sounding dari Timbangan bertanggal
	sama, tapi cuma sekali — waktu Get Data ditekan. Timbangan yang masuk
	sesudah soundingnya disubmit, atau yang dibatalkan belakangan, tidak pernah
	terbaca lagi, jadi pengiriman dan produksi hari itu berhenti di keadaan
	waktu tombol itu ditekan.

	Tidak berhenti di hari itu: produksi jadi Stock Entry, dan Stock Entry itu
	yang membentuk stock awal sounding hari berikutnya.

	Tipe timbangannya tidak disaring, cuma jenis barangnya. Query pengiriman di
	kedua sounding juga tidak menyaring tipe — yang dijumlahkan seluruh Timbangan
	submitted hari itu untuk barang bertipe CPO atau Palm Kernel — jadi
	pemicunya harus melihat rentang yang sama persis dengan yang dibaca.

	Selama tidak ada sounding submitted di tanggal itu atau sesudahnya, tidak
	ada yang diantrikan: angkanya akan terbaca sendiri waktu Get Data ditekan
	dan belum ada Stock Entry yang bisa meleset. Timbangan hari ini yang
	soundingnya belum dibuat berhenti di satu query.

	Dikerjakan di latar belakang, bukan di dalam transaksi submit. Fase Stock
	Entry membatalkan lalu membuat ulang dokumen stok dan sempat mematikan
	larangan stok minus — pekerjaan yang tidak boleh menumpang di request orang
	yang cuma menimbang truk.
	"""
	if not (doc.kode_barang and doc.unit and doc.posting_date):
		return

	tipe_barang = frappe.db.get_value("Item", doc.kode_barang, "tipe_barang")

	doctype = next(
		(nama for nama, cfg in REKAP_SOUNDING.items() if cfg["tipe_barang"] == tipe_barang),
		None,
	)

	if not doctype:
		return

	if not frappe.db.exists(doctype, {
		"unit": doc.unit,
		"docstatus": 1,
		"tanggal_proses": (">=", doc.posting_date),
	}):
		return

	# Sengaja tidak di-deduplicate: kalau satu job sedang jalan, enqueue
	# berikutnya akan dilewati frappe, dan timbangan yang baru saja masuk ikut
	# hilang dari hitungan. Jobnya idempoten, jadi jalan dua kali lebih murah
	# daripada tidak jalan sama sekali.
	frappe.enqueue(
		"sth.mill.rekap_sounding.hitung_ulang_rekap",
		queue="long",
		timeout=3600,
		# Wajib: tanpa ini jobnya bisa mulai sebelum submit-nya ter-commit, dan
		# yang dibaca query pengiriman masih keadaan sebelum timbangan ini.
		enqueue_after_commit=True,
		doctype=doctype,
		unit=doc.unit,
		sejak=doc.posting_date,
	)

	frappe.msgprint(
		_("{0} unit {1} sejak {2} dihitung ulang di latar belakang, termasuk Stock Entry-nya.").format(
			doctype, doc.unit, frappe.format(doc.posting_date, {"fieldtype": "Date"})),
		alert=True,
		indicator="blue",
	)


def hitung_ulang_dokumen_sesudahnya(doc):
	"""Sounding sesudah dokumen ini dihitung ulang, dipanggil dari on_submit/on_cancel.

	Produksi dokumen ini jadi Stock Entry, dan Stock Entry itu yang membentuk
	stock awal dokumen sesudahnya. Jadi begitu dokumen ini disubmit atau
	dibatalkan, seluruh sounding sesudahnya di unit yang sama ikut bergeser.

	Dikerjakan langsung, bukan di latar belakang seperti pemicu Timbangan: orang
	yang menekan submit memang sedang menunggu angkanya, dan rantainya biasanya
	pendek. Larangan stok minus tidak dimatikan dan tidak ada commit di
	tengah — keduanya akan merusak transaksi submit yang sedang berjalan.
	"""
	hitung_ulang_rekap(
		doc.doctype,
		doc.unit,
		add_days(doc.tanggal_proses, 1),
		izinkan_minus=False,
		commit=False,
	)
