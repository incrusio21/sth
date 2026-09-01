import frappe

from sth.mill.doctype.security_check_point.security_check_point import (
	get_kendaraan_by_no_pol,
	get_nama_operator,
)

# Maksimal no polisi tak terdaftar yang dirinci di ringkasan, supaya output bench
# migrate tidak kebanjiran kalau masternya memang banyak yang bolong.
BATAS_RINCIAN = 20


def execute(scp_names=None):
	"""Isi data kendaraan dan supir di dokumen lama kiriman API.

	Security Check Point dari API cuma membawa no polisi; nama supir dan platnya
	baru diisi dari master Alat Berat Dan Kendaraan sejak set_data_kendaraan ada
	di controller. Dokumen yang telanjur masuk sebelum itu ditambal di sini,
	berikut SPB dan Timbangan yang menempel padanya:

	    Security Check Point : no_polisi, license_plate, driver_name
	    Surat Pengantar Buah : kendaraan, no_polisi, driver_code
	    Timbangan            : no_polisi, driver_name

	Di Security Check Point nilainya ditimpa supaya formatnya ikut master. Di SPB
	dan Timbangan cuma field yang masih kosong yang diisi — keduanya punya jalur
	API sendiri yang datanya lebih lengkap, dan itu tidak boleh tertindih.

	No polisinya dicari berurutan dari Security Check Point sendiri, lalu SPB, lalu
	Timbangan-nya: field no_polisi di SCP menarik nilai dari spb.no_polisi, jadi
	dokumen yang SPB-nya masih stub bisa jadi platnya sudah hilang di sana padahal
	masih tersimpan di dokumen tetangganya.

	Untuk dokumen tertentu, panggil dari bench console:

	    from sth.patches.isi_data_kendaraan_security_check_point import execute
	    execute(["REC-01-09-26-001"])
	"""
	rows = _get_scp_rows(scp_names)
	if not rows:
		print("Data kendaraan API: tidak ada Security Check Point yang perlu ditambal")
		return

	nama_operator = {}
	jumlah = {"scp": 0, "spb": 0, "timbangan": 0}
	tanpa_no_polisi = []
	tidak_terdaftar = {}

	for row in rows:
		no_polisi = _cari_no_polisi(row)

		if not no_polisi:
			tanpa_no_polisi.append(row.name)
			continue

		kendaraan = get_kendaraan_by_no_pol(no_polisi)

		if not kendaraan:
			# Platnya tetap dikembalikan ke Security Check Point walau kendaraannya
			# tidak ada di master, supaya dokumennya tidak tinggal kosong.
			tidak_terdaftar[no_polisi] = tidak_terdaftar.get(no_polisi, 0) + 1
			jumlah["scp"] += _tulis("Security Check Point", row.name, {"no_polisi": no_polisi}, hanya_kosong=True)
			continue

		if kendaraan.operator not in nama_operator:
			nama_operator[kendaraan.operator] = get_nama_operator(kendaraan.operator) if kendaraan.operator else None

		driver_name = nama_operator[kendaraan.operator]

		jumlah["scp"] += _tulis("Security Check Point", row.name, {
			"no_polisi": kendaraan.no_pol,
			"license_plate": kendaraan.no_pol,
			"driver_name": driver_name,
		})

		jumlah["spb"] += _isi_spb(row.spb, kendaraan)
		jumlah["timbangan"] += _isi_timbangan(row, kendaraan, driver_name)

	_cetak_ringkasan(jumlah, tanpa_no_polisi, tidak_terdaftar)


def _get_scp_rows(scp_names):
	filters = {"docstatus": ["<", 2]}

	if scp_names:
		if isinstance(scp_names, str):
			scp_names = [n.strip() for n in scp_names.split(",")]

		filters["name"] = ["in", [n for n in scp_names if n]]
	else:
		# Cuma kiriman API yang ditambal: dokumen dari UI platnya diisi orang yang
		# melihat kendaraannya langsung, dan itu lebih dipercaya daripada master.
		filters["owner"] = ["like", "%api@sth%"]

	return frappe.get_all(
		"Security Check Point",
		filters=filters,
		fields=["name", "no_polisi", "license_plate", "spb"],
		limit_page_length=0,
	)


def _cari_no_polisi(row):
	"""No polisi dokumen ini, dicari sampai ke SPB dan Timbangan-nya."""
	if row.no_polisi:
		return row.no_polisi

	if row.license_plate:
		return row.license_plate

	if row.spb:
		no_polisi = frappe.db.get_value("Surat Pengantar Buah", row.spb, "no_polisi")
		if no_polisi:
			return no_polisi

	for timbangan in _get_timbangan_rows(row):
		if timbangan.no_polisi:
			return timbangan.no_polisi

	return None


def _get_timbangan_rows(row):
	"""Timbangan milik Security Check Point ini.

	Timbangan kiriman API tidak mengisi ticket_number — map_api_ticket_number
	mengosongkannya — jadi sambungannya lewat SPB. Yang dari UI tetap dicari
	lewat ticket_number.

	Hasilnya ditempel ke row karena dipakai dua kali: waktu mencari no polisi dan
	waktu mengisi Timbangan-nya.
	"""
	if row.get("timbangan_rows") is not None:
		return row.timbangan_rows

	fields = ["name", "no_polisi", "driver_name"]
	rows = frappe.get_all(
		"Timbangan",
		filters={"ticket_number": row.name, "docstatus": ["<", 2]},
		fields=fields,
		limit_page_length=0,
	)

	if row.spb:
		terambil = {r.name for r in rows}
		rows += [
			r
			for r in frappe.get_all(
				"Timbangan",
				filters={"spb": row.spb, "docstatus": ["<", 2]},
				fields=fields,
				limit_page_length=0,
			)
			if r.name not in terambil
		]

	row.timbangan_rows = rows

	return rows


def _isi_spb(spb, kendaraan):
	if not spb:
		return 0

	doc = frappe.db.get_value(
		"Surat Pengantar Buah",
		spb,
		["tipe_kendaraan", "kendaraan_eksternal"],
		as_dict=True,
	)

	# SPB kendaraan luar punya masternya sendiri (Driver); jangan dipasangi
	# kendaraan internal.
	if not doc or doc.kendaraan_eksternal or doc.tipe_kendaraan == "Eksternal":
		return 0

	return _tulis("Surat Pengantar Buah", spb, {
		"kendaraan": kendaraan.name,
		"no_polisi": kendaraan.no_pol,
		"driver_code": kendaraan.operator,
	}, hanya_kosong=True)


def _isi_timbangan(row, kendaraan, driver_name):
	terisi = 0

	for timbangan in _get_timbangan_rows(row):
		terisi += _tulis("Timbangan", timbangan.name, {
			"no_polisi": kendaraan.no_pol,
			"driver_name": driver_name,
		}, hanya_kosong=True)

	return terisi


def _tulis(doctype, name, values, hanya_kosong=False):
	"""Tulis field yang isinya belum sesuai, kembalikan 1 kalau ada yang berubah.

	Langsung lewat db.set_value karena dokumennya banyak yang sudah submit, dan
	patch ini cuma memasang data master tanpa mengubah angka timbangan apa pun.
	"""
	sekarang = frappe.db.get_value(doctype, name, list(values), as_dict=True)
	if not sekarang:
		return 0

	berubah = {}

	for fieldname, value in values.items():
		if not value:
			continue

		lama = sekarang.get(fieldname)

		if hanya_kosong:
			if lama:
				continue
		elif lama == value:
			continue

		berubah[fieldname] = value

	if not berubah:
		return 0

	frappe.db.set_value(doctype, name, berubah, update_modified=False)

	return 1


def _cetak_ringkasan(jumlah, tanpa_no_polisi, tidak_terdaftar):
	print(
		"Data kendaraan API: {scp} Security Check Point, {spb} SPB, "
		"{timbangan} Timbangan diperbarui".format(**jumlah)
	)

	if tanpa_no_polisi:
		print(
			"  {0} Security Check Point tidak punya no polisi di dokumen mana pun, dilewati".format(
				len(tanpa_no_polisi)
			)
		)

	if not tidak_terdaftar:
		return

	print("  {0} no polisi tidak ada di master Alat Berat Dan Kendaraan:".format(len(tidak_terdaftar)))

	terurut = sorted(tidak_terdaftar.items(), key=lambda item: (-item[1], item[0]))

	for no_polisi, dokumen in terurut[:BATAS_RINCIAN]:
		print("    {0} ({1} dokumen)".format(no_polisi, dokumen))

	sisa = len(terurut) - BATAS_RINCIAN

	if sisa > 0:
		print("    ... dan {0} no polisi lainnya".format(sisa))
