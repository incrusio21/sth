import frappe
from frappe.utils import cint, flt

from sth.plantation.doctype.alat_berat_dan_kendaraan.alat_berat_dan_kendaraan import sync_kmhm_akhir

# BKM Traksi yang tidak punya BKM Traksi sebelumnya sebagai acuan. KM/HM awalnya
# diambil dari kolom "KMHM Awal (Task)" baris pertama di file import aslinya.
ACUAN_EXCEL = {
	"BKM-TRK-01646": 515208,  # Buku Kerja Mandor Traksi BUS SEKOLAH SEPTEMBER 2026.xlsx
	"BKM-TRK-01521": 283067,  # Buku Kerja Mandor Traksi SEPTEMBER 2026 28-30 DT.xlsx
	"BKM-TRK-01081": 5194,  # Buku Kerja Mandor Traksi genset agustus 2026.xlsx
}


def execute(terapkan=0, kendaraan=None, dari=None, sampai=None, acuan=None):
	"""Isi KM/HM BKM Traksi dan BKM Bengkel yang tertinggal 0.

	Ada tiga sumber nol yang saling menular:
	- Import BKM Traksi sebelum feb4e232 mengambil KM/HM awal dari kolom header
	  Excel yang kosong, jadi header dan baris kegiatan pertama bernilai 0.
	- KM/HM akhir BKM Bengkel diisi manual dan sering dibiarkan kosong (0).
	- sync_kmhm_akhir lalu menyalin 0 itu ke master kendaraan, sehingga BKM
	  Bengkel berikutnya mengambil KM/HM awal 0 juga.

	Per kendaraan, BKM Traksi dan Bengkel submitted ditelusuri urut waktu
	(urutan yang sama dengan get_latest_kmhm), sambil membawa KM/HM akhir BKM
	Traksi terakhir:
	- Traksi dengan KM/HM awal 0: header dan kegiatan baris pertama diisi
	  KM/HM akhir Traksi sebelumnya.
	- Bengkel: KM/HM awal dan akhir disamakan dengan KM/HM akhir Traksi
	  sebelumnya (kendaraan di bengkel tidak berjalan). KM/HM Bengkel sendiri
	  tidak dipakai sebagai acuan, lihat catatan di telusuri_kendaraan.
	Yang tidak punya riwayat sebelumnya, atau riwayatnya melebihi KM/HM akhir
	dokumen itu, dilaporkan dan dibiarkan.

	`acuan` ({nama BKM Traksi: KM/HM awal}, bawaannya ACUAN_EXCEL) mengisi
	Traksi dengan KM/HM awal 0 dari sumber lain, misalnya file import aslinya.
	Nilainya didahulukan dari KM/HM akhir Traksi sebelumnya.

	    bench --site <site> execute sth.patches.perbaiki_kmhm_bkm.execute
	    bench --site <site> execute sth.patches.perbaiki_kmhm_bkm.execute \\
	        --kwargs "{'terapkan': 1}"

	Penyaringnya: kendaraan, dari, sampai (posting date dokumen yang diubah;
	riwayat sebelum `dari` tetap dipakai sebagai acuan). Patch ini aman diulang.

	Premi alat berat dan costing yang sudah terbentuk tidak dihitung ulang.
	Baris yang premi-nya ikut dihitung dari KM/HM yang salah dicetak supaya
	bisa ditindaklanjuti. Sengaja tidak didaftarkan di patches.txt.
	"""
	terapkan = cint(terapkan)
	acuan = ACUAN_EXCEL if acuan is None else (frappe.parse_json(acuan) if isinstance(acuan, str) else acuan)
	print("Mode {0}\n".format("TERAPKAN" if terapkan else "LAPORAN SAJA"))

	ubah = []
	lewati = []
	for kend in daftar_kendaraan(kendaraan):
		telusuri_kendaraan(kend, dari, sampai, ubah, lewati, acuan)

	for u in ubah:
		print("{doctype:8} {name:15} {posting_date} {kendaraan:12} {field:20} {lama:>12} -> {baru:>12}".format(**u))
	print("\n{0} perubahan field di {1} dokumen".format(len(ubah), len({u["name"] for u in ubah})))

	if lewati:
		print("\nDilewati (perlu dicek manual):")
		for l in lewati:
			print("{doctype:8} {name:15} {posting_date} {kendaraan:12} {alasan}".format(**l))

	premi = [u for u in ubah if u.get("premi")]
	if premi:
		print("\nPremi alat berat yang dihitung dari KM/HM awal 0 (tidak diubah patch ini):")
		for u in premi:
			print("{name:15} {posting_date} {kendaraan:12} premi {premi:>15,.0f}".format(**u))

	if not terapkan:
		return

	for u in ubah:
		if u["child"]:
			frappe.db.set_value(u["child_doctype"], u["child"], "kmhm_awal", u["baru"], update_modified=False)
		else:
			frappe.db.set_value(u["doctype_full"], u["name"], u["field"], u["baru"], update_modified=False)

	for name, doctype in {(u["name"], u["doctype_full"]) for u in ubah}:
		catatan = "; ".join(
			"{0} {1:g} -> {2:g}".format(u["field"], u["lama"], u["baru"])
			for u in ubah if u["name"] == name
		)
		frappe.get_doc({
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": doctype,
			"reference_name": name,
			"content": "KM/HM diperbaiki (sth.patches.perbaiki_kmhm_bkm): " + catatan,
		}).insert(ignore_permissions=True)

	for kend in sorted({u["kendaraan"] for u in ubah}):
		sync_kmhm_akhir(kend)

	frappe.db.commit()
	print("\nDiterapkan. KM/HM akhir master kendaraan disinkron ulang.")


def daftar_kendaraan(kendaraan=None):
	if kendaraan:
		return [kendaraan]

	return frappe.db.sql_list("""
		SELECT kendaraan FROM `tabBuku Kerja Mandor Traksi`
		WHERE docstatus = 1 AND IFNULL(kendaraan, '') != ''
		UNION
		SELECT kd_kndr FROM `tabBuku Kerja Mandor Bengkel`
		WHERE docstatus = 1 AND IFNULL(kd_kndr, '') != ''
	""")


def telusuri_kendaraan(kendaraan, dari, sampai, ubah, lewati, acuan):
	dokumen = frappe.db.sql("""
		SELECT * FROM (
			SELECT 'Traksi' AS jenis, name, posting_date, kmhm_awal, kmhm_akhir,
				posting_datetime AS sort_dt, creation
			FROM `tabBuku Kerja Mandor Traksi`
			WHERE docstatus = 1 AND kendaraan = %(kendaraan)s

			UNION ALL

			SELECT 'Bengkel', name, posting_date, kmhm_awal, kmhm_akhir,
				CONCAT(posting_date, ' 23:59:59'), creation
			FROM `tabBuku Kerja Mandor Bengkel`
			WHERE docstatus = 1 AND kd_kndr = %(kendaraan)s
		) t
		ORDER BY sort_dt, creation
	""", {"kendaraan": kendaraan}, as_dict=True)

	terakhir = 0
	for d in dokumen:
		awal, akhir = flt(d.kmhm_awal), flt(d.kmhm_akhir)
		dalam_rentang = (not dari or str(d.posting_date) >= str(dari)) and (
			not sampai or str(d.posting_date) <= str(sampai)
		)

		def catat(field, lama, baru, child=None, premi=0):
			ubah.append({
				"doctype": d.jenis,
				"doctype_full": "Buku Kerja Mandor " + d.jenis,
				"child_doctype": "Detail BKM Traksi Kegiatan",
				"name": d.name,
				"posting_date": d.posting_date,
				"kendaraan": kendaraan,
				"field": field,
				"lama": lama,
				"baru": baru,
				"child": child,
				"premi": premi,
			})

		def tolak(alasan):
			lewati.append({"doctype": d.jenis, "name": d.name, "posting_date": d.posting_date,
				"kendaraan": kendaraan, "alasan": alasan})

		if d.jenis == "Traksi":
			if not awal and akhir and dalam_rentang:
				task = frappe.db.get_value(
					"Detail BKM Traksi Kegiatan",
					{"parent": d.name, "parenttype": "Buku Kerja Mandor Traksi", "idx": 1},
					["name", "kmhm_awal", "kmhm_akhir", "premi_heavy_equipment"],
					as_dict=True,
				)
				sumber = "acuan" if d.name in acuan else "BKM sebelumnya"
				nilai = flt(acuan[d.name]) if d.name in acuan else terakhir
				if not nilai:
					tolak("KM/HM awal 0, tidak ada BKM sebelumnya sebagai acuan")
				elif not task or nilai > flt(task.kmhm_akhir):
					tolak("KM/HM awal dari {0} {1:g} melebihi KM/HM akhir kegiatan pertama {2:g}".format(
						sumber, nilai, flt(task.kmhm_akhir) if task else 0))
				else:
					catat("kmhm_awal", awal, nilai)
					if not flt(task.kmhm_awal):
						catat("task#1 kmhm_awal", flt(task.kmhm_awal), nilai, child=task.name,
							premi=flt(task.premi_heavy_equipment))

			if akhir:
				terakhir = akhir
			continue

		# Bengkel: template import-nya tidak punya kolom KM/HM, jadi KM/HM awalnya
		# diambil dari master kendaraan saat diinput, bukan saat tanggal posting.
		# Untuk BKM yang diinput mundur nilainya bisa melompat melewati BKM Traksi
		# di tanggal itu. Karena itu Bengkel disamakan dengan KM/HM akhir Traksi
		# sebelumnya dan tidak dipakai sebagai acuan dokumen berikutnya.
		if not dalam_rentang:
			continue

		if terakhir:
			if awal != terakhir:
				catat("kmhm_awal", awal, terakhir)
			if akhir != terakhir:
				catat("kmhm_akhir", akhir, terakhir)
		elif not awal and not akhir:
			tolak("KM/HM awal dan akhir 0, tidak ada BKM Traksi sebelumnya sebagai acuan")
		elif akhir < awal:
			catat("kmhm_akhir", akhir, awal)
