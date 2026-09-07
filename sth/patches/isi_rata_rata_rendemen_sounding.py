import frappe
from frappe.utils import flt, get_first_day, getdate

from sth.mill.utils import RENDEMEN_BULANAN


def execute():
	"""Isi ulang Rata-rata OER/KER Bulan Ini di dokumen sounding yang sudah ada.

	Batas atas rata-ratanya berubah: dulu sampai akhir bulan Tanggal Proses,
	sekarang berhenti di Tanggal Proses dokumennya sendiri. Nilai yang tersimpan
	di dokumen lama masih hasil rumus yang lama, dan sebagian dokumen bahkan
	belum pernah punya isi karena fieldnya baru ada sesudah dokumennya disubmit.

	Yang tampil di form sebenarnya sudah benar tanpa patch ini — dihitung ulang
	tiap dokumen dibuka. Yang salah adalah kolom di database, dan itulah yang
	dibaca list view, report view, dan ekspor.

	Rumusnya persis sama dengan set_rata_rata_rendemen_bulanan: rata-rata netto 2
	dokumen submitted di unit yang sama, sejak awal bulan sampai tanggal proses
	dokumen itu, tidak ditimbang jumlah TBS olah. Dokumen di tanggal yang sama
	saling ikut menghitung, sesuai `between` di query aslinya.

	Semua dokumen dihitung sekaligus di Python, bukan satu query per dokumen:
	rata-rata berjalan cuma butuh satu kali baca seluruh dokumen per doctype.

	Cuma satu field keterangan yang disentuh. Produksi, OER, KER, dan Stock
	Entry-nya tidak ikut berubah, jadi patch ini aman dijalankan ulang — dokumen
	yang angkanya sudah cocok dilewati.
	"""
	for doctype, (rendemen, target) in RENDEMEN_BULANAN.items():
		print("{0}: {1} dokumen diperbarui.".format(
			doctype, isi_dokumen(doctype, rendemen, target)
		))


def isi_dokumen(doctype, rendemen, target):
	dokumen = frappe.get_all(
		doctype,
		filters={"docstatus": ("<", 2)},
		fields=["name", "unit", "tanggal_proses", "docstatus", rendemen, target],
		order_by="unit asc, tanggal_proses asc",
		limit_page_length=0,
	)

	if not dokumen:
		print("Tidak ada {0}, dilewati.".format(doctype))
		return 0

	kumulatif = kumpulkan(dokumen, rendemen)
	diperbarui = 0

	for row in dokumen:
		if not (row.unit and row.tanggal_proses):
			continue

		jumlah, banyak = kumulatif[kunci(row)][getdate(row.tanggal_proses)]
		baru = jumlah / banyak if banyak else 0.0

		if flt(row.get(target), 6) == flt(baru, 6):
			continue

		# Langsung ke kolomnya: dokumennya kebanyakan sudah disubmit dan yang
		# diisi cuma satu field keterangan yang read only di form.
		frappe.db.set_value(doctype, row.name, target, baru, update_modified=False)
		diperbarui += 1

	frappe.db.commit()

	return diperbarui


def kumpulkan(dokumen, rendemen):
	"""Jumlah dan banyaknya rendemen submitted sampai tiap tanggal, per unit per bulan.

	Dokumen draft ikut dapat tanggalnya sendiri di hasil — supaya fieldnya tetap
	terisi — tapi rendemennya tidak ikut menjumlah, sama seperti query aslinya
	yang cuma menghitung docstatus 1.
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

		isi = harian.setdefault(kunci(row), {}).setdefault(tanggal, [0.0, 0])
		isi[0] += flt(row.get(rendemen))
		isi[1] += 1

	kumulatif = {}

	for kunci_bulan, tanggal_set in tanggal_dipakai.items():
		per_tanggal = harian.get(kunci_bulan, {})
		jumlah = 0.0
		banyak = 0
		hasil = {}

		for tanggal in sorted(tanggal_set):
			if tanggal in per_tanggal:
				jumlah += per_tanggal[tanggal][0]
				banyak += per_tanggal[tanggal][1]

			hasil[tanggal] = (jumlah, banyak)

		kumulatif[kunci_bulan] = hasil

	return kumulatif


def kunci(row):
	"""Rata-ratanya per unit per bulan, jadi itu juga kunci pengelompokannya."""
	return (row.unit, getdate(get_first_day(row.tanggal_proses)))
