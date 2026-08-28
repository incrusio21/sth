import frappe
from frappe.utils import flt

DOCTYPE = "Sounding Stock Palm Kernel di Bunker Kernel"


def execute():
	"""Hitung ulang sounding Palm Kernel: hasil sounding, stock akhir, produksi, dan STE-nya.

	Rumusnya berubah: stock akhir sekarang adalah volume sounding itu sendiri,
	dan produksi = stock akhir - stock awal + pengiriman. Stock awal tidak lagi
	diambil dari saldo Stock Ledger melainkan dari stock akhir sounding
	sebelumnya di unit yang sama, urut menurut tanggal proses.

	Karena itu dokumennya tidak bisa diperbaiki satu-satu: stock akhir sebuah
	dokumen menentukan stock awal dokumen berikutnya, jadi seluruh dokumen per
	unit diproses berurutan sambil membawa stock akhir terakhir. Dokumen
	pertama tiap unit tidak punya pendahulu, stock awalnya dibiarkan apa adanya.

	Hasil sounding dibangun ulang dari Ukuran Detail supaya ikut master Ukuran
	Bunker Kernel Silo yang sekarang. Baris rekap yang ukurannya tidak ketemu di
	master - netto-nya dulu diisi tangan lewat tombol Hitung Limas - netto
	lamanya dipakai kembali, bukan ditimpa nol. Dokumen tanpa Ukuran Detail
	tidak dibangun ulang sama sekali karena rekapnya cuma ada di dokumen.

	Untuk dokumen yang sudah submit, Stock Entry lama di-cancel lalu dihapus dan
	dibuat ulang dari produksi yang baru. Produksi negatif keluar sebagai
	Material Issue, mengikuti penanganan di Sounding Stock CPO di BST.

	Kalau ada dokumen yang gagal, patch ini sengaja berhenti dengan error supaya
	tidak ada rantai stock awal yang setengah jadi. Aman dijalankan ulang:
	semuanya dihitung ulang dari sumbernya.
	"""
	dokumen = frappe.get_all(
		DOCTYPE,
		filters={"docstatus": ("<", 2)},
		fields=["name", "unit"],
		order_by="unit asc, tanggal_proses asc, creation asc",
		limit_page_length=0,
	)

	if not dokumen:
		print("Tidak ada {0}, dilewati.".format(DOCTYPE))
		return

	stock_akhir_sebelumnya = {}
	berubah = ste_dibuat = 0

	for row in dokumen:
		doc = frappe.get_doc(DOCTYPE, row.name)
		produksi_lama = flt(doc.produksi)
		stock_akhir_lama = flt(doc.stock_akhir)

		hitung_ulang(doc, stock_akhir_sebelumnya)
		simpan(doc)

		stock_akhir_sebelumnya[doc.unit] = flt(doc.stock_akhir)

		if flt(doc.produksi) != produksi_lama or flt(doc.stock_akhir) != stock_akhir_lama:
			berubah += 1

		if doc.docstatus == 1 and perlu_ste_baru(doc, produksi_lama):
			ste_dibuat += buat_ulang_ste(doc)

	print("{0} dari {1} dokumen sounding Palm Kernel dihitung ulang, {2} Stock Entry dibuat ulang.".format(
		berubah, len(dokumen), ste_dibuat
	))


def hitung_ulang(doc, stock_akhir_sebelumnya):
	"""Bangun ulang hasil sounding, lalu hitung stock akhir dan produksinya."""
	if doc.ukuran_detail:
		netto_manual = {
			(baris.idx, baris.kompartemen): flt(baris.netto)
			for baris in doc.rekap_hasil or []
		}

		doc.hasil_titik_sounding = []
		doc.rekap_hasil = []
		doc.calculate_hasil_titik_sounding()
		doc.add_rekap_hasil()

		kembalikan_netto_manual(doc, netto_manual)

	doc.calculate_volume_sounding()

	if doc.unit in stock_akhir_sebelumnya:
		doc.stock_awal = stock_akhir_sebelumnya[doc.unit]

	doc.hitung_produksi()


def kembalikan_netto_manual(doc, netto_manual):
	"""Pakai lagi netto hasil hitung limas untuk baris yang volumenya nol.

	Ukuran yang tidak ada di Ukuran Bunker Kernel Silo Detail menghasilkan
	volume nol, dan netto-nya dihitung tangan lewat tombol Hitung Limas. Baris
	itu dicocokkan lewat urutan dan nama kompartemennya.
	"""
	for baris in doc.rekap_hasil:
		if flt(baris.volume) > 0:
			continue

		lama = netto_manual.get((baris.idx, baris.kompartemen))
		if lama:
			baris.netto = lama


def simpan(doc):
	"""Simpan tanpa lewat save(), karena dokumennya sudah submit."""
	for fieldname in ("hasil_titik_sounding", "rekap_hasil"):
		for baris in doc.get(fieldname) or []:
			baris.docstatus = doc.docstatus

	doc.db_update()
	doc.update_children()


def perlu_ste_baru(doc, produksi_lama):
	"""STE dibuat ulang kalau produksinya berubah, atau belum punya STE sama sekali.

	Yang kedua untuk dokumen berproduksi negatif: dulu on_submit melewatinya
	karena syaratnya produksi > 0, jadi stoknya tidak pernah dikeluarkan.
	"""
	if flt(doc.produksi) != produksi_lama:
		return True

	if not flt(doc.produksi):
		return False

	return not frappe.db.exists("Stock Entry", {"references": doc.name, "docstatus": 1})


def buat_ulang_ste(doc):
	for row in frappe.get_all("Stock Entry", filters={"references": doc.name}, fields=["name", "docstatus"]):
		ste = frappe.get_doc("Stock Entry", row.name)
		if ste.docstatus == 1:
			ste.cancel()
		ste.delete()

	if not flt(doc.produksi):
		return 0

	doc.create_ste()
	return 1
