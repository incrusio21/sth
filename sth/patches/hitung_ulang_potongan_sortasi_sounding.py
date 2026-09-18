import frappe
from frappe.utils import flt, getdate

from sth.mill.doctype.sounding_stock_cpo_di_bst.sounding_stock_cpo_di_bst import (
	SoundingStockCPOdiBST,
)
from sth.mill.doctype.sounding_stock_palm_kernel_di_bunker_kernel.sounding_stock_palm_kernel_di_bunker_kernel import (
	SoundingStockPalmKerneldiBunkerKernel,
)
from sth.mill.utils import get_potongan_sortasi

# Dua sounding dibedakan cuma oleh nama fieldnya. Rumus rendemennya dipinjam dari
# doctype masing-masing, bukan disalin ke sini, supaya tidak ada salinan kedua
# yang ketinggalan kalau penjaga penyebutnya berubah lagi.
SOUNDING = (
	{
		"doctype": "Sounding Stock CPO di BST",
		"sortasi": "potongan_sortasi",
		"produksi": "produksi_cpo",
		"netto_1": "oer_netto_1",
		"netto_2": "oer_netto_2",
		"hitung": SoundingStockCPOdiBST.calculate_oer_netto,
	},
	{
		"doctype": "Sounding Stock Palm Kernel di Bunker Kernel",
		"sortasi": "sortasi",
		"produksi": "produksi",
		"netto_1": "ker_netto_1",
		"netto_2": "ker_netto_2",
		"hitung": SoundingStockPalmKerneldiBunkerKernel.hitung_ker_netto,
	},
)

# Presisi pembanding: rendemen mengikuti field Percent-nya, potongan sortasi
# mengikuti float precision bawaan. Cuma dipakai untuk memutuskan satu dokumen
# perlu ditulis ulang atau tidak, bukan untuk membulatkan nilai yang disimpan.
PRESISI_PERSEN = 2
PRESISI_BERAT = 3


def execute(dari="2026-09-01", sampai="2026-09-30", dry_run=True):
	"""Hitung ulang potongan sortasi Sounding CPO & Kernel, berikut rendemennya.

	Sampai perubahan aturan sortasi, potongan yang tersimpan cuma sortasi hari
	itu sendiri. Hari yang pabriknya tidak mengolah karena itu menyimpan potongan
	yang tidak pernah terpakai, dan hari olah berikutnya menyimpan potongan yang
	terlalu kecil untuk TBS yang sebenarnya diolah. Script ini menuliskan angka
	yang sama dengan yang dihasilkan tombol Get Data sekarang: akumulasi sejak
	hari sesudah pabrik terakhir mengolah sampai tanggal prosesnya.

	Yang ditulis cuma tiga kolom — potongan sortasi dan sepasang rendemen. Stock
	awal, produksi, tbs olah, dan Stock Entry-nya tidak tersentuh sama sekali,
	jadi stok maupun jurnal tidak bergeser. Rata-rata rendemen bulanan juga tidak
	ikut: penyebutnya tbs olah apa adanya, bukan yang dikurangi sortasi.

	Default-nya dry run dan default rentangnya September 2026::

	    bench --site <site> execute sth.patches.hitung_ulang_potongan_sortasi_sounding.execute
	    bench --site <site> execute sth.patches.hitung_ulang_potongan_sortasi_sounding.execute --args "['2026-09-01','2026-09-30',0]"

	Sengaja tidak didaftarkan di patches.txt: perbaikan data sekali jalan yang
	angkanya mau dilihat dulu. Aman dijalankan ulang — dokumen yang angkanya
	sudah cocok dilewati, dan dokumen batal tidak ikut.
	"""
	dari, sampai = getdate(dari), getdate(sampai)

	print("Potongan sortasi {0} s/d {1}{2}".format(
		dari, sampai, " (dry run)" if dry_run else ""
	))

	for setelan in SOUNDING:
		proses_doctype(setelan, dari, sampai, dry_run)

	if dry_run:
		print("Dry run: tidak ada yang ditulis. Ulangi dengan dry_run=False.")
		return

	frappe.db.commit()


def proses_doctype(setelan, dari, sampai, dry_run):
	doctype = setelan["doctype"]
	f_sortasi, f_produksi = setelan["sortasi"], setelan["produksi"]
	f_netto_1, f_netto_2 = setelan["netto_1"], setelan["netto_2"]

	diperbarui = 0
	diperiksa = 0

	for row in frappe.get_all(
		doctype,
		filters={
			"docstatus": ("<", 2),
			"tanggal_proses": ("between", [dari, sampai]),
		},
		fields=["name", "unit", "pabrik", "tanggal_proses", "tbs_olah",
			f_produksi, f_sortasi, f_netto_1, f_netto_2],
		order_by="tanggal_proses asc, creation asc",
		limit_page_length=0,
	):
		diperiksa += 1

		sortasi = get_potongan_sortasi(row.unit, row.tanggal_proses, row.pabrik)

		# Yang dikirim ke rumusnya cuma field yang dia baca, dengan sortasi versi
		# baru. Produksi dan tbs olah dipakai apa adanya dari dokumennya.
		hitung = frappe._dict({
			f_produksi: row.get(f_produksi),
			"tbs_olah": row.tbs_olah,
			f_sortasi: sortasi,
		})
		setelan["hitung"](hitung)

		baru = {
			f_sortasi: sortasi,
			f_netto_1: flt(hitung.get(f_netto_1), PRESISI_PERSEN),
			f_netto_2: flt(hitung.get(f_netto_2), PRESISI_PERSEN),
		}

		lama = {
			f_sortasi: flt(row.get(f_sortasi), PRESISI_BERAT),
			f_netto_1: flt(row.get(f_netto_1), PRESISI_PERSEN),
			f_netto_2: flt(row.get(f_netto_2), PRESISI_PERSEN),
		}

		banding = dict(baru, **{f_sortasi: flt(sortasi, PRESISI_BERAT)})

		if lama == banding:
			continue

		print("  {0} {1} {2}: sortasi {3} -> {4}, {5} {6} -> {7}".format(
			row.name, row.tanggal_proses, row.unit,
			lama[f_sortasi], flt(sortasi, PRESISI_BERAT),
			f_netto_2, lama[f_netto_2], baru[f_netto_2],
		))

		diperbarui += 1

		if dry_run:
			continue

		# Langsung ke kolomnya: sebagian dokumennya sudah disubmit, dan yang
		# diisi cuma field turunan yang read only di form.
		frappe.db.set_value(doctype, row.name, baru, update_modified=False)

	print("{0}: {1} dari {2} dokumen {3}.".format(
		doctype, diperbarui, diperiksa,
		"perlu dihitung ulang" if dry_run else "dihitung ulang",
	))
