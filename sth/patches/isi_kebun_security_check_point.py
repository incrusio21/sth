import frappe

# Batas rincian yang dicetak, supaya output bench tidak kebanjiran kalau yang
# perlu diisi ternyata banyak.
BATAS_RINCIAN = 20


def execute(names=None):
	"""Isi kebun di Security Check Point dari unit SPB-nya.

	Field `kebun` baru ditambahkan, jadi semua dokumen pos yang sudah ada masih
	kosong. Isinya di-fetch dari spb.unit, tapi fetch cuma jalan waktu dokumen
	posnya sendiri disimpan — padahal urutan lazimnya kebalikannya: pos duluan,
	SPB-nya menyusul, dan dokumen pos tidak pernah disimpan lagi sesudah itu.

	Dokumen baru sudah tertutup _resync_security_check_point di Surat Pengantar
	Buah, yang mendorong unit SPB ke sini tiap kiriman SPB masuk. Yang tersisa
	dokumen lama, dan itu yang diurus di sini.

	Field `unit` tidak disentuh: itu pabrik tempat posnya berdiri, dan
	get_security_location memakainya dengan arti itu.

	Ditulis lewat db.set_value karena hampir semua dokumennya sudah submit, dan
	kebun read-only ber-fetch_from sehingga menyimpan lewat dokumen tidak
	mengubah apa-apa. Yang sudah dibatalkan dilewati, begitu juga yang kebunnya
	sudah sama — patch ini aman dijalankan berulang.

	Untuk sebagian dokumen saja:

	    from sth.patches.isi_kebun_security_check_point import execute
	    execute(["SCP-00123", "SCP-00124"])
	"""
	baris = _baris_beda(names)

	if not baris:
		print("Kebun Security Check Point: tidak ada baris yang perlu diisi")
		return

	for b in baris:
		frappe.db.set_value("Security Check Point", b.name, "kebun", b.unit_spb)

	frappe.db.commit()

	_cetak_ringkasan(baris)


def _baris_beda(names):
	"""Dokumen pos yang kebunnya berbeda dari unit SPB yang ditunjuknya."""
	if isinstance(names, str):
		names = [n.strip() for n in names.split(",")]

	names = [n for n in (names or []) if n]

	syarat = ""
	nilai = {}

	if names:
		syarat = "AND scp.name IN %(names)s"
		nilai["names"] = tuple(names)

	return frappe.db.sql("""
		SELECT scp.name, scp.kebun AS kebun_lama, spb.unit AS unit_spb
		FROM `tabSecurity Check Point` scp
		INNER JOIN `tabSurat Pengantar Buah` spb ON spb.name = scp.spb
		WHERE scp.docstatus < 2
			AND IFNULL(spb.unit, '') != ''
			AND IFNULL(scp.kebun, '') != spb.unit
			{syarat}
		ORDER BY scp.name
	""".format(syarat=syarat), nilai, as_dict=True)


def _cetak_ringkasan(baris):
	rekap = {}

	for b in baris:
		kunci = (b.kebun_lama or "", b.unit_spb)
		rekap[kunci] = rekap.get(kunci, 0) + 1

	print(f"Kebun Security Check Point: {len(baris)} dokumen diisi dari unit SPB-nya")

	for (lama, baru), jumlah in sorted(rekap.items(), key=lambda pasangan: -pasangan[1]):
		print(f"  {lama or '(kosong)'} -> {baru}: {jumlah} dokumen")

	for b in baris[:BATAS_RINCIAN]:
		print(f"  {b.name}: {b.kebun_lama or '(kosong)'} -> {b.unit_spb}")

	if len(baris) > BATAS_RINCIAN:
		print(f"  ... dan {len(baris) - BATAS_RINCIAN} dokumen lain")
