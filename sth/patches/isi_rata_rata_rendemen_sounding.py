import frappe
from frappe.utils import flt, get_first_day, getdate

from sth.mill.utils import RENDEMEN_BULANAN, hitung_rendemen


def execute():
	"""Isi ulang Rata-rata OER/KER Bulan Ini di dokumen sounding yang sudah ada.

	Rumusnya berubah: dulu rata-rata harian sederhana atas angka persen tiap
	dokumen, sekarang ditimbang tonase — total produksi dibagi total TBS olah
	netto 2 sejak awal bulan sampai tanggal proses dokumen itu, dikali 100. Nilai
	yang tersimpan di dokumen lama masih hasil rumus yang lama.

	Yang tampil di form sebenarnya sudah benar tanpa patch ini — dihitung ulang
	tiap dokumen dibuka. Yang salah adalah kolom di database, dan itulah yang
	dibaca list view, report view, ekspor, dan OER/KER di COGS Mill dan Kebun.

	Rumusnya persis sama dengan set_rata_rata_rendemen_bulanan, sampai ke
	pembaginya yang dikurangi potongan sortasi. Cuma dokumen submitted yang
	menjumlah, dan dokumen di tanggal yang sama saling ikut menghitung, sesuai
	`between` di query aslinya.

	Semua dokumen dihitung sekaligus di Python, bukan satu query per dokumen:
	rata-rata berjalan cuma butuh satu kali baca seluruh dokumen per doctype.

	Cuma satu field keterangan yang disentuh. Produksi, OER, KER, dan Stock
	Entry-nya tidak ikut berubah, jadi patch ini aman dijalankan ulang — dokumen
	yang angkanya sudah cocok dilewati.
	"""
	for doctype, cfg in RENDEMEN_BULANAN.items():
		print("{0}: {1} dokumen diperbarui.".format(doctype, isi_dokumen(doctype, cfg)))


def isi_dokumen(doctype, cfg):
	dokumen = frappe.get_all(
		doctype,
		filters={"docstatus": ("<", 2)},
		fields=[
			"name",
			"unit",
			"tanggal_proses",
			"docstatus",
			cfg["produksi"],
			cfg["tbs_olah"],
			cfg["sortasi"],
			cfg["target"],
		],
		order_by="unit asc, tanggal_proses asc",
		limit_page_length=0,
	)

	if not dokumen:
		print("Tidak ada {0}, dilewati.".format(doctype))
		return 0

	kumulatif = kumpulkan(dokumen, cfg)
	diperbarui = 0

	for row in dokumen:
		if not (row.unit and row.tanggal_proses):
			continue

		produksi, penyebut = kumulatif[kunci(row)][getdate(row.tanggal_proses)]
		baru = hitung_rendemen(produksi, penyebut)

		if flt(row.get(cfg["target"]), 6) == flt(baru, 6):
			continue

		# Langsung ke kolomnya: dokumennya kebanyakan sudah disubmit dan yang
		# diisi cuma satu field keterangan yang read only di form.
		frappe.db.set_value(doctype, row.name, cfg["target"], baru, update_modified=False)
		diperbarui += 1

	frappe.db.commit()

	return diperbarui


def kumpulkan(dokumen, cfg):
	"""Total produksi dan total TBS olah netto 2 submitted sampai tiap tanggal,
	per unit per bulan.

	Dokumen draft ikut dapat tanggalnya sendiri di hasil — supaya fieldnya tetap
	terisi — tapi angkanya tidak ikut menjumlah, sama seperti query aslinya yang
	cuma menghitung docstatus 1.
	"""
	harian = {}
	tanggal_dipakai = {}

	for row in dokumen:
		if not (row.unit and row.tanggal_proses):
			continue

		tanggal = getdate(row.tanggal_proses)
		tanggal_dipakai.setdefault(kunci(row), set()).add(tanggal)

		if row.docstatus != 1:
			continue

		isi = harian.setdefault(kunci(row), {}).setdefault(tanggal, [0.0, 0.0])
		isi[0] += flt(row.get(cfg["produksi"]))
		isi[1] += flt(row.get(cfg["tbs_olah"])) - flt(row.get(cfg["sortasi"]))

	kumulatif = {}

	for kunci_bulan, tanggal_set in tanggal_dipakai.items():
		per_tanggal = harian.get(kunci_bulan, {})
		produksi = 0.0
		penyebut = 0.0
		hasil = {}

		for tanggal in sorted(tanggal_set):
			if tanggal in per_tanggal:
				produksi += per_tanggal[tanggal][0]
				penyebut += per_tanggal[tanggal][1]

			hasil[tanggal] = (produksi, penyebut)

		kumulatif[kunci_bulan] = hasil

	return kumulatif


def kunci(row):
	"""Rata-ratanya per unit per bulan, jadi itu juga kunci pengelompokannya."""
	return (row.unit, getdate(get_first_day(row.tanggal_proses)))
