import frappe
from frappe.utils import flt

from sth.mill.utils import izinkan_stock_minus

DOCTYPE = "Sounding Stock Palm Kernel di Bunker Kernel"
CHILD_REKAP = "Ukuran Volume Sounding Bunker"

# Selisih di bawah ini dianggap sama, supaya pembulatan float tidak dilaporkan
# sebagai kejanggalan.
TOLERANSI = 0.005


def execute():
	"""Batalkan semua Stock Entry sounding Palm Kernel, lalu cetak hitungannya.

	Dipakai untuk mengosongkan Stock Ledger dari penerimaan sounding Palm Kernel
	supaya angkanya bisa diperiksa dokumen per dokumen sebelum dibuat ulang.
	STE-nya cuma dibatalkan, tidak dihapus, jadi masih bisa dilihat saat
	memeriksa. Angka di dokumen soundingnya sendiri tidak disentuh sama sekali.

	Setelah angkanya beres, jalankan sth.patches.hitung_ulang_sounding_palm_kernel
	untuk membangun ulang STE-nya - patch itu menghapus STE batal yang tersisa
	sebelum membuat yang baru.

	Tiap dokumen dicetak satu baris berisi stock awal, stock akhir, volume
	sounding, pengiriman, dan produksi, dengan tanda kalau ada yang tidak cocok:

	  RUMUS   produksi bukan stock akhir - stock awal + pengiriman
	  VOLUME  stock akhir tidak sama dengan volume sounding
	  REKAP   volume sounding tidak sama dengan jumlah netto rekap hasil
	  RANTAI  stock awal bukan stock akhir dokumen sebelumnya di unit itu

	Patch ini sengaja tidak didaftarkan di patches.txt. Membatalkan STE bukan
	sesuatu yang boleh jalan sendiri tiap migrate - jalankan lewat bench execute
	saat memang dibutuhkan. Aman diulang: STE yang sudah batal dilewati.
	"""
	dokumen = frappe.get_all(
		DOCTYPE,
		filters={"docstatus": ("<", 2)},
		fields=[
			"name", "unit", "tanggal_proses",
			"stock_awal", "stock_akhir", "volume_sounding", "pengiriman", "produksi",
		],
		order_by="unit asc, tanggal_proses asc, creation asc",
		limit_page_length=0,
	)

	if not dokumen:
		print("Tidak ada {0}, dilewati.".format(DOCTYPE))
		return

	dibatalkan = 0
	stock_akhir_sebelumnya = {}
	janggal = []

	cetak_kepala()

	with izinkan_stock_minus():
		for row in dokumen:
			dibatalkan += batalkan_ste(row.name)
			frappe.db.commit()

			catatan = periksa_hitungan(row, stock_akhir_sebelumnya)
			cetak_baris(row, catatan)

			if catatan:
				janggal.append(row.name)

			stock_akhir_sebelumnya[row.unit] = flt(row.stock_akhir)

	print("")
	print("{0} Stock Entry dibatalkan dari {1} dokumen sounding Palm Kernel.".format(
		dibatalkan, len(dokumen)
	))

	if janggal:
		print("{0} dokumen hitungannya janggal: {1}".format(len(janggal), ", ".join(janggal)))
	else:
		print("Hitungan semua dokumen cocok.")


def batalkan_ste(nama_sounding):
	"""Batalkan Stock Entry dokumen ini, biarkan yang sudah batal apa adanya."""
	dibatalkan = 0

	for row in frappe.get_all(
		"Stock Entry",
		filters={"references": nama_sounding, "docstatus": 1},
		pluck="name",
	):
		frappe.get_doc("Stock Entry", row).cancel()
		dibatalkan += 1

	return dibatalkan


def periksa_hitungan(row, stock_akhir_sebelumnya):
	"""Kumpulkan tanda kejanggalan hitungan satu dokumen."""
	catatan = []

	produksi_semestinya = flt(row.stock_akhir) - flt(row.stock_awal) + flt(row.pengiriman)
	if beda(row.produksi, produksi_semestinya):
		catatan.append("RUMUS")

	if beda(row.stock_akhir, row.volume_sounding):
		catatan.append("VOLUME")

	# Volume sounding dibulatkan ke puluhan terdekat oleh controller, jadi yang
	# dibandingkan jumlah netto yang sudah dibulatkan dengan cara yang sama.
	if beda(row.volume_sounding, round(flt(jumlah_netto_rekap(row.name)), -1)):
		catatan.append("REKAP")

	if row.unit in stock_akhir_sebelumnya and beda(row.stock_awal, stock_akhir_sebelumnya[row.unit]):
		catatan.append("RANTAI")

	return catatan


def jumlah_netto_rekap(nama_sounding):
	hasil = frappe.db.sql("""
		select sum(netto)
		from `tab{0}`
		where parent = %s and parenttype = %s and parentfield = 'rekap_hasil'
	""".format(CHILD_REKAP), (nama_sounding, DOCTYPE))

	return hasil[0][0] if hasil and hasil[0][0] is not None else 0


def beda(kiri, kanan):
	return abs(flt(kiri) - flt(kanan)) > TOLERANSI


def cetak_kepala():
	print("{0:<14} {1:<8} {2:<12} {3:>12} {4:>12} {5:>12} {6:>12} {7:>12}  {8}".format(
		"Dokumen", "Unit", "Tgl Proses",
		"Stock Awal", "Stock Akhir", "Volume", "Pengiriman", "Produksi", "Catatan",
	))


def cetak_baris(row, catatan):
	print("{0:<14} {1:<8} {2:<12} {3:>12.0f} {4:>12.0f} {5:>12.0f} {6:>12.0f} {7:>12.0f}  {8}".format(
		row.name,
		row.unit or "-",
		str(row.tanggal_proses or "-"),
		flt(row.stock_awal),
		flt(row.stock_akhir),
		flt(row.volume_sounding),
		flt(row.pengiriman),
		flt(row.produksi),
		" ".join(catatan),
	))
