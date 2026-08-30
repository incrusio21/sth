import frappe
from frappe.utils import flt, getdate

from sth.mill.utils import buat_ulang_ste_sounding, izinkan_stock_minus

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

	Dokumen yang rekapnya nol semua - ukurannya tidak ada di master - volume
	soundingnya ikut jadi nol, tidak memakai total lama yang masih tersimpan di
	induknya. Total lama itu tidak bisa dipercaya: SSPKDBK-0008 misalnya
	menghasilkan KER 64%, padahal wajarnya 4-6%. Konsekuensinya penerimaan
	stoknya ikut terhapus, dan produksi yang hilang itu muncul lagi di sounding
	berikutnya karena stock awalnya jadi nol - totalnya tetap, cuma pembagian
	per harinya yang meleset sampai masternya dilengkapi dan patch ini
	dijalankan ulang. Dokumen yang kena didaftar di akhir.

	Untuk dokumen yang sudah submit, Stock Entry lama di-cancel lalu dihapus dan
	dibuat ulang dari produksi yang baru. Produksi negatif keluar sebagai
	Material Issue, mengikuti penanganan di Sounding Stock CPO di BST. STE yang
	posting_date-nya tidak sama dengan tanggal soundingnya ikut dibuat ulang,
	untuk membetulkan STE yang terlanjur bertanggal hari pembuatannya.

	Tiap dokumen di-commit begitu selesai. Kalau ada yang gagal, patch berhenti
	dengan error tapi dokumen yang sudah beres tidak ikut hangus, dan patch ini
	aman dijalankan ulang: semuanya dihitung ulang dari sumbernya, dan dokumen
	yang produksinya sudah benar tidak menyentuh Stock Entry-nya lagi.
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
	volume_dinolkan = []
	berubah = ste_dibuat = 0

	with izinkan_stock_minus():
		for urutan, row in enumerate(dokumen, 1):
			doc = frappe.get_doc(DOCTYPE, row.name)
			produksi_lama = flt(doc.produksi)
			stock_akhir_lama = flt(doc.stock_akhir)

			if hitung_ulang(doc, stock_akhir_sebelumnya):
				volume_dinolkan.append(doc.name)

			simpan(doc)

			stock_akhir_sebelumnya[doc.unit] = flt(doc.stock_akhir)

			if flt(doc.produksi) != produksi_lama or flt(doc.stock_akhir) != stock_akhir_lama:
				berubah += 1

			if doc.docstatus == 1 and perlu_ste_baru(doc, produksi_lama):
				ste_dibuat += buat_ulang_ste_sounding(doc, doc.produksi)

			frappe.db.commit()
			print("[{0}/{1}] {2} selesai.".format(urutan, len(dokumen), doc.name))

	print("{0} dari {1} dokumen sounding Palm Kernel dihitung ulang, {2} Stock Entry dibuat ulang.".format(
		berubah, len(dokumen), ste_dibuat
	))

	laporkan_volume_dinolkan(volume_dinolkan)
	laporkan_stock_minus()
	laporkan_antrian_repost()


def laporkan_volume_dinolkan(nama_dokumen):
	"""Daftar dokumen yang volume soundingnya jadi nol.

	Ukurannya tidak ada di Ukuran Bunker Kernel Silo Detail, jadi rekapnya nol
	semua dan produksinya ikut nol. Penerimaan stok dokumen ini terhapus, dan
	produksinya pindah ke sounding berikutnya.
	"""
	if not nama_dokumen:
		return

	print("{0} dokumen volume soundingnya jadi nol karena ukurannya tidak ada di master:".format(
		len(nama_dokumen)
	))
	for nama in nama_dokumen:
		print("  {0}".format(nama))
	print("Lengkapi Ukuran Bunker Kernel Silo Detail untuk ukuran tersebut, lalu jalankan patch ini lagi.")


def laporkan_stock_minus():
	"""Ingatkan kalau saldo Palm Kernel masih ada yang minus.

	Larangan stok minus sudah dinyalakan lagi di akhir patch, jadi gudang yang
	saldonya masih minus akan menolak transaksi berikutnya sampai selisihnya
	dibereskan.
	"""
	item_code = frappe.db.get_value("Item", {"tipe_barang": "Palm Kernel"})
	if not item_code:
		return

	minus = frappe.db.sql("""
		select warehouse, min(qty_after_transaction) as terendah
		from `tabStock Ledger Entry`
		where item_code = %s and is_cancelled = 0 and qty_after_transaction < 0
		group by warehouse
	""", item_code, as_dict=True)

	if not minus:
		return

	print("Perhatian, saldo Palm Kernel masih minus di:")
	for row in minus:
		print("  {0}: terendah {1}".format(row.warehouse, row.terendah))


def laporkan_antrian_repost():
	"""Penilaian stok dihitung ulang oleh scheduler, bukan oleh patch ini.

	STE bertanggal mundur bikin ERPNext mengantrikan Repost Item Valuation.
	Menjalankannya di dalam patch bisa memakan waktu berjam-jam dan menahan
	migrate, jadi biar scheduler yang mengerjakan.
	"""
	antri = frappe.db.count("Repost Item Valuation", {"status": ("in", ("Queued", "In Progress"))})
	if antri:
		print("{0} Repost Item Valuation mengantre, nilai stok menyesuaikan setelah scheduler selesai.".format(antri))


def hitung_ulang(doc, stock_akhir_sebelumnya):
	"""Bangun ulang hasil sounding, lalu hitung stock akhir dan produksinya.

	Mengembalikan True kalau volume soundingnya yang tadinya terisi jadi nol,
	tanda ukurannya tidak ada di master.
	"""
	volume_lama = flt(doc.volume_sounding)

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

	volume_hilang = bool(volume_lama and not flt(doc.volume_sounding))

	if doc.unit in stock_akhir_sebelumnya:
		doc.stock_awal = stock_akhir_sebelumnya[doc.unit]

	doc.hitung_produksi()

	return volume_hilang


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
	"""STE dibuat ulang kalau produksinya berubah, belum ada, atau salah tanggal.

	Belum ada: dokumen berproduksi negatif dulu dilewati on_submit karena
	syaratnya produksi > 0, jadi stoknya tidak pernah dikeluarkan.

	Salah tanggal: STE yang dibuat sebelum set_posting_time dinyalakan kena
	timpa validate_posting_time, posting_date-nya jadi hari STE itu dibuat dan
	bukan tanggal soundingnya.
	"""
	if flt(doc.produksi) != produksi_lama:
		return True

	if not flt(doc.produksi):
		return False

	posting_date = frappe.db.get_value(
		"Stock Entry",
		{"references": doc.name, "docstatus": 1},
		"posting_date",
	)

	if not posting_date:
		return True

	return getdate(posting_date) != getdate(doc.tanggal)
