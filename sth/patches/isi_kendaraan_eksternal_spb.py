import frappe

from sth.plantation.doctype.surat_pengantar_buah.surat_pengantar_buah import (
	get_plat_driver,
	turunkan_kendaraan_eksternal,
)


def execute(spb_names=None):
	"""Isi no polisi dan supir dokumen lama dari SPB kendaraan eksternal.

	SPB eksternal tidak pernah punya no_polisi — set_missing_value dulu
	membandingkan tipe_kendaraan dengan "External", yang tidak ada di opsinya — dan
	pos maupun timbangannya tidak pernah membawa plat dan supirnya:

	    Surat Pengantar Buah : no_polisi dari plat Driver kendaraan_eksternal
	    Security Check Point : no_polisi, license_plate, driver_name
	    Timbangan            : no_polisi, driver_name

	Cuma SPB yang diinput lewat form, dan di pos serta timbangannya juga cuma yang
	bukan kiriman API — turunkan_kendaraan_eksternal yang memilahnya. Ditulis
	lewat db.set_value tanpa menyentuh modified, karena dokumennya banyak yang
	sudah submit dan yang berubah cuma data kendaraan.

	Untuk SPB tertentu, panggil dari bench console:

	    from sth.patches.isi_kendaraan_eksternal_spb import execute
	    execute(["SPB-40167"])
	"""
	filters = {
		"tipe_kendaraan": "Eksternal",
		"docstatus": ["<", 2],
		"owner": ["not like", "%api@sth%"],
	}

	if spb_names:
		if isinstance(spb_names, str):
			spb_names = [n.strip() for n in spb_names.split(",")]

		filters["name"] = ["in", [n for n in spb_names if n]]

	rows = frappe.get_all(
		"Surat Pengantar Buah",
		filters=filters,
		fields=["name", "owner", "tipe_kendaraan", "kendaraan_eksternal", "driver_name", "driver_eksternal", "no_polisi"],
		limit_page_length=0,
	)

	jumlah = {"Surat Pengantar Buah": 0, "Security Check Point": 0, "Timbangan": 0}
	tanpa_plat = []

	for row in rows:
		plat = get_plat_driver(row.kendaraan_eksternal)

		if not plat:
			tanpa_plat.append(row.name)
		elif row.no_polisi != plat:
			frappe.db.set_value("Surat Pengantar Buah", row.name, "no_polisi", plat, update_modified=False)
			jumlah["Surat Pengantar Buah"] += 1

		for doctype, n in turunkan_kendaraan_eksternal(row, update_modified=False).items():
			jumlah[doctype] += n

	print(
		"Kendaraan eksternal SPB: {0} SPB diperiksa, {1} SPB, {2} Security Check Point, "
		"{3} Timbangan diperbarui".format(
			len(rows),
			jumlah["Surat Pengantar Buah"],
			jumlah["Security Check Point"],
			jumlah["Timbangan"],
		)
	)

	if tanpa_plat:
		print(
			"  {0} SPB Driver-nya tanpa custom_license_plate, no polisinya tetap kosong: {1}".format(
				len(tanpa_plat), ", ".join(tanpa_plat)
			)
		)
