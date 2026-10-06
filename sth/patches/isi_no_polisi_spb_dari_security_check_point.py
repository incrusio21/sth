import frappe

# Batas rincian yang dicetak, supaya output bench tidak kebanjiran kalau yang
# perlu diisi ternyata banyak.
BATAS_RINCIAN = 20


def execute(names=None):
	"""Isi no polisi dan nama supir SPB yang masih kosong dari Security Check Point-nya.

	Pos mencatat kendaraan yang benar-benar lewat — no_polisi dan driver_name
	kiriman API, atau license_plate hasil scan QR Driver — sedangkan SPB-nya bisa
	saja tidak pernah diisi. Plat diambil dari no_polisi SCP dulu, lalu
	license_plate.

	Tiap field diisi sendiri-sendiri dan cuma kalau kosong di SPB; yang sudah
	terisi tidak ditimpa walau berbeda dengan pos. Kalau satu SPB lewat lebih dari
	satu pos, yang submit didahulukan, lalu yang terakhir dibuat — dan kalau
	isinya berbeda-beda, SPB-nya dicetak di ringkasan supaya bisa diperiksa.

	Ditulis lewat db.set_value tanpa menyentuh modified karena kebanyakan SPB
	sudah submit dan yang berubah cuma data kendaraan. Aman dijalankan berulang.

	Untuk sebagian dokumen saja:

	    from sth.patches.isi_no_polisi_spb_dari_security_check_point import execute
	    execute(["SPB-00123", "SPB-00124"])
	"""
	if isinstance(names, str):
		names = [n.strip() for n in names.split(",")]

	names = [n for n in (names or []) if n]

	per_spb = {}

	for row in _baris_kosong(names):
		spb = per_spb.setdefault(row.spb, {"lama": row, "no_polisi": [], "driver_name": []})

		plat = (row.no_polisi or "").strip() or (row.license_plate or "").strip()
		if plat:
			spb["no_polisi"].append(plat)

		supir = (row.driver_name or "").strip()
		if supir:
			spb["driver_name"].append(supir)

	jumlah = {"no_polisi": 0, "driver_name": 0}
	beda = []

	for spb, data in per_spb.items():
		nilai = {}

		for field in jumlah:
			# Field yang sudah terisi di SPB tidak disentuh. Baris sudah terurut,
			# jadi isian pertama yang dipakai.
			if (data["lama"].get("spb_" + field) or "").strip() or not data[field]:
				continue

			nilai[field] = data[field][0]
			jumlah[field] += 1

			if len(set(data[field])) > 1:
				beda.append((spb, field, data[field]))

		if nilai:
			frappe.db.set_value("Surat Pengantar Buah", spb, nilai, update_modified=False)

	frappe.db.commit()

	_cetak_ringkasan(jumlah, beda)


def _baris_kosong(names):
	"""Security Check Point milik SPB yang no polisi atau supirnya kosong, yang terpakai dulu."""
	syarat = ""
	nilai = {}

	if names:
		syarat = "AND spb.name IN %(names)s"
		nilai["names"] = tuple(names)

	return frappe.db.sql("""
		SELECT spb.name AS spb, spb.no_polisi AS spb_no_polisi, spb.driver_name AS spb_driver_name,
			scp.no_polisi, scp.license_plate, scp.driver_name
		FROM `tabSurat Pengantar Buah` spb
		INNER JOIN `tabSecurity Check Point` scp ON scp.spb = spb.name AND scp.docstatus < 2
		WHERE spb.docstatus < 2
			AND (IFNULL(TRIM(spb.no_polisi), '') = '' OR IFNULL(TRIM(spb.driver_name), '') = '')
			{syarat}
		ORDER BY spb.name, scp.docstatus DESC, scp.creation DESC
	""".format(syarat=syarat), nilai, as_dict=True)


def _cetak_ringkasan(jumlah, beda):
	print(
		"SPB dari Security Check Point: no polisi {no_polisi} SPB, nama supir {driver_name} SPB diisi".format(
			**jumlah
		)
	)

	if not beda:
		return

	print(f"  {len(beda)} isian berbeda antar pos untuk SPB yang sama, periksa:")

	for spb, field, isi in beda[:BATAS_RINCIAN]:
		lainnya = ", ".join(sorted(set(isi[1:]) - {isi[0]}))
		print(f"    {spb} {field}: {isi[0]} (lainnya: {lainnya})")

	if len(beda) > BATAS_RINCIAN:
		print(f"    ... dan {len(beda) - BATAS_RINCIAN} lainnya")
