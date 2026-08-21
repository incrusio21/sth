import frappe
from frappe.utils import cint, flt

from sth.accounting_sth.doctype.asset_scrap_request.asset_scrap_request import (
	nilai_perolehan_porsi,
	pengajuan_berlaku,
	perbarui_ringkasan_scrap,
)


def execute():
	"""Isi ringkasan scrap di Asset dan luruskan qty yang terlanjur dibulatkan.

	Tiga hal yang dibereskan sekaligus untuk asset yang sudah pernah discrap:

	1. Qty discrap dulu dibulatkan ke unit utuh dan dipaksa minimal 1, jadi asset
	   ber-qty 1 yang discrap 50% tercatat discrap 1 unit — sisanya nol padahal
	   separuh nilainya masih di buku. Sekarang qty mengikuti persentasenya.
	2. asset_quantity dulu ikut dikurangi waktu scrap sebagian. Angka itu kini
	   dibekukan sebagai qty awal, jadi yang terlanjur menyusut dikembalikan ke
	   nilainya semula supaya Sisa Qty tidak terpotong dua kali.
	3. Nominal Awal, Nominal Total Scrap, Qty Sudah Discrap, dan Sisa Qty di
	   Asset diisi dari pengajuan yang berlaku.
	"""
	for asset in asset_pernah_discrap():
		berlaku = pengajuan_berlaku(asset)
		if not berlaku:
			continue

		qty_awal = kembalikan_qty_awal(asset, berlaku)
		luruskan_qty_pengajuan(berlaku, qty_awal)
		isi_nilai_perolehan_awal(asset, berlaku)

		# qty_scrap di dokumen sudah diluruskan, ringkasannya menyusul dari situ
		perbarui_ringkasan_scrap(asset)

	frappe.db.commit()


def asset_pernah_discrap():
	return frappe.db.sql_list("""
		SELECT DISTINCT asr.asset
		FROM `tabAsset Scrap Request` asr
		JOIN `tabAsset` a ON a.name = asr.asset
		WHERE asr.docstatus = 1
	""")


def luruskan_qty_pengajuan(berlaku, qty_awal):
	"""Hitung ulang qty_scrap tiap pengajuan dari persentasenya.

	Yang tersimpan di pengajuan lama hasil pembulatan ke unit utuh. Nilai
	rupiahnya tidak ikut berubah — pembagian nilai sejak dulu memang bersandar
	pada persentase, bukan pada qty ini.

	Ditelusuri urut waktu karena persentase tiap pengajuan berlaku atas sisa yang
	ada saat itu, sama seperti nilai rupiahnya dulu dihitung.
	"""
	sisa = flt(qty_awal)

	for d in sorted(berlaku, key=lambda d: d.creation):
		persentase = flt(d.persentase_scrap) or 100
		qty = sisa if persentase >= 100 else flt(sisa * persentase / 100.0, 4)

		if flt(d.qty_scrap) != qty:
			frappe.db.set_value(
				"Asset Scrap Request", d.name, "qty_scrap", qty, update_modified=False
			)

		d.qty_scrap = qty
		sisa = max(sisa - qty, 0)


def kembalikan_qty_awal(asset, berlaku):
	"""Kembalikan asset_quantity ke qty sebelum ada scrap.

	Patokannya asset_quantity yang terpotret di pengajuan paling awal: angka itu
	diambil dari Asset sebelum satu pun porsi dikurangi. Balikannya qty awal itu,
	dipakai sebagai dasar penelusuran qty tiap pengajuan.
	"""
	sekarang = cint(frappe.db.get_value("Asset", asset, "asset_quantity")) or 1
	terlama = min(berlaku, key=lambda d: d.creation)

	qty_awal = cint(terlama.asset_quantity) or sekarang

	if qty_awal != sekarang:
		frappe.db.set_value(
			"Asset", asset, "asset_quantity", qty_awal, update_modified=False
		)

	return qty_awal


def isi_nilai_perolehan_awal(asset, berlaku):
	"""Potret harga perolehan sebelum scrap, disusun mundur dari nilai sekarang.

	Yang mengurangi gross_purchase_amount di Asset cuma scrap sebagian; scrap
	100% membiarkan angkanya utuh dan hanya mengubah status. Jadi yang
	ditambahkan balik hanya porsi milik pengajuan sebagian.
	"""
	sebagian = [d for d in berlaku if flt(d.persentase_scrap) < 100]

	gross = flt(frappe.db.get_value("Asset", asset, "gross_purchase_amount"))
	awal = gross + sum(nilai_perolehan_porsi(d) for d in sebagian)

	frappe.db.set_value(
		"Asset", asset, "nilai_perolehan_awal", flt(awal, 2), update_modified=False
	)
