import frappe
from frappe.utils import flt

from sth.mill.doctype.data_tbs.data_tbs import get_total_tbs

# posting_ulang_ste dipinjam dari patch restan, bukan disalin: membatalkan lalu
# membuat ulang Stock Entry bertanggal mundur itu bagian yang paling mudah salah,
# dan dua salinan yang lama-lama berbeda lebih berbahaya daripada satu impor
# antar-patch. Keduanya juga sama-sama patch manual yang tidak akan dihapus.
from sth.patches.perbaiki_restan_data_tbs import posting_ulang_ste

DOCTYPE = "Data TBS"


def execute():
	"""Baca ulang Jumlah TBS Diterima dengan rumus yang berlaku sekarang.

	`get_total_tbs` dulu menjumlahkan `netto_2` — netto sesudah potongan sortasi.
	Sejak commit 600f92ad (11 September 2026) yang dijumlahkan `netto`, yaitu
	bruto dikurangi tara tanpa potongan. Dokumen yang dibuat sebelum tanggal itu
	menyimpan angka basis lama dan tidak akan pernah menyusul sendiri: field ini
	cuma ditulis di `get_data`, yaitu waktu tombol Get Data ditekan, dan tidak
	pernah dihitung ulang di `validate` seperti halnya restan awal.

	Selisihnya searah dan tidak kecil — DTBS-0066 menyimpan 323.733,47 sedangkan
	rumus sekarang memberi 335.190,00 untuk timbangan yang sama.

	Sekalian ikut terbawa: perubahan Timbangan yang terjadi sesudah Get Data
	ditekan. DTBS-0068 misalnya menyimpan angka yang masih memuat TBG-11180,
	timbangan yang dibatalkan dua jam sesudah dokumennya disimpan.

	Restan awalnya ikut dirantai ulang. Jumlah TBS Diterima masuk ke Grand Total
	TBS, yang membagi diri jadi tbs olah, tbs restan, dan tbs loading ramp, dan
	Total TBS Restan-nya jadi restan awal hari berikutnya — jadi satu dokumen
	yang berubah menggeser seluruh hari sesudahnya di unit yang sama.

	Fase satu memperbaiki angka dokumennya, fase dua memposting ulang Stock
	Entry-nya. Dipisah supaya kalau pembatalan STE tertahan periode akuntansi
	yang sudah tutup, angka dokumennya tetap sudah benar.

	Aman dijalankan ulang: dokumen yang angkanya sudah cocok dan STE-nya sudah
	benar dilewati. Dokumen batal tidak ikut.
	"""
	dokumen = frappe.get_all(
		DOCTYPE,
		filters={"docstatus": ("<", 2)},
		fields=["name", "unit", "tanggal_produksi"],
		order_by="unit asc, tanggal_produksi asc, creation asc",
		limit_page_length=0,
	)

	if not dokumen:
		print("Tidak ada Data TBS, dilewati.")
		return

	kembar = cari_kembar(dokumen)
	laporkan_kembar(kembar)

	dikerjakan = [row for row in dokumen if kunci(row) not in kembar]

	diperbaiki = hitung_ulang_dokumen(dokumen, kembar)
	print("{0} dari {1} Data TBS dibaca ulang Jumlah TBS Diterima-nya.".format(
		diperbaiki, len(dikerjakan)))

	posting_ulang_ste(dikerjakan)


def kunci(row):
	return (row.unit, str(row.tanggal_produksi))


def cari_kembar(dokumen):
	"""unit + tanggal yang punya lebih dari satu dokumen hidup.

	Hari kembar tidak boleh ikut dibaca ulang. `get_total_tbs` menjumlahkan
	seluruh timbangan sehari penuh tanpa tahu dokumen mana yang seharusnya
	memikulnya, jadi dua dokumen di hari yang sama akan sama-sama diberi total
	penuh dan hari itu masuk dua kali ke rantai restan.

	Dokumen seperti ini tidak bisa dibuat lagi — `validate_duplikat` menolaknya —
	tapi yang telanjur ada sejak sebelum penjagaan itu masih tertinggal. Mana
	yang harus dibatalkan adalah keputusan orang, bukan tebakan patch.
	"""
	hitung = {}

	for row in dokumen:
		hitung.setdefault(kunci(row), []).append(row.name)

	return {k: v for k, v in hitung.items() if len(v) > 1}


def laporkan_kembar(kembar):
	if not kembar:
		return

	print("Hari dengan lebih dari satu Data TBS — dilewati, angkanya dibiarkan apa adanya:")
	for (unit, tanggal), nama in sorted(kembar.items(), key=lambda item: item[0][1]):
		print("  {0} {1}: {2}".format(unit, tanggal, ", ".join(nama)))
	print("  Batalkan yang berlebih dulu, lalu jalankan patch ini lagi.")


def hitung_ulang_dokumen(dokumen, kembar):
	"""Isi ulang TBS diterima tiap dokumen, lalu rantai restan awalnya per unit."""
	restan = {}
	diperbaiki = 0

	for row in dokumen:
		doc = frappe.get_doc(DOCTYPE, row.name)

		if kunci(row) in kembar:
			# Dilewati, tapi rantainya tetap diteruskan dari angka tersimpannya:
			# hari sesudahnya tidak boleh ikut hilang cuma karena hari ini kembar.
			restan[doc.unit] = flt(doc.total_tbs_restan)
			continue

		# Dibulatkan dulu sebelum dibanding: nilai yang dibaca dari kolom decimal
		# selalu beda di digit terakhir dari hasil hitungan float.
		sebelum = angka_turunan(doc)

		# flt: get_total_tbs memulangkan None kalau tidak ada timbangan sama
		# sekali di hari itu — SUM atas nol baris itu NULL, bukan 0.
		doc.jumlah_tbs_diterima = flt(get_total_tbs(doc.tanggal_produksi, doc.unit))
		doc.jumlah_tbs_restan = restan.get(doc.unit, 0)
		doc.calculate_totals()
		restan[doc.unit] = flt(doc.total_tbs_restan)

		if angka_turunan(doc) == sebelum:
			continue

		# db_update, bukan save: dokumennya sudah disubmit dan yang diubah cuma
		# angka turunan yang seluruhnya read only di form.
		doc.db_update()
		diperbaiki += 1

	frappe.db.commit()

	return diperbaiki


def angka_turunan(doc):
	# Presisi field tidak dipakai: total_tbs_restan presisinya 0 supaya tampil
	# bulat di form, padahal selisih setengah kilo tetap harus ikut dibetulkan.
	return tuple(flt(doc.get(field), 3) for field in (
		"jumlah_tbs_diterima", "jumlah_tbs_restan", "grand_total_tbs",
		"berat_rata_rata_tbs", "tbs_olah", "tbs_restan", "tbs_loading_ramp",
		"total_tbs_restan",
	))
