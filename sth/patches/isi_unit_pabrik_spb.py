import frappe

# Batas rincian yang dicetak, supaya output bench tidak kebanjiran kalau yang
# perlu diisi ternyata banyak.
BATAS_RINCIAN = 20


def execute(names=None):
	"""Isi unit pabrik di SPB dari unit timbangan yang menimbangnya.

	Field `unit_pabrik` baru ditambahkan, jadi semua SPB yang sudah ada masih
	kosong. Pabrik penerima cuma pasti di timbangannya: `unit` di Timbangan
	dipaksa ke unit ber-mill 1 milik company, sedangkan SPB sendiri hanya tahu
	kebun pengirimnya.

	Dokumen baru sudah tertutup Timbangan.update_spb_weight, yang mengisinya
	waktu hasil timbang disalin ke SPB — jalur yang sama dipakai ulang oleh
	_resync_timbangan kalau janjangnya berubah belakangan.

	Field `pabrik` tidak disentuh: itu Link Mill Master dan isian tangan, beda
	arti dengan yang ini.

	Yang dipakai timbangan yang sudah submit. Kalau satu SPB punya lebih dari
	satu — seharusnya tidak, tapi datanya yang menentukan — yang terakhir
	menimbang yang dipakai, sama seperti urutan update_spb_weight dijalankan.

	Ditulis lewat db.set_value karena hampir semua SPB-nya sudah submit, dan
	unit_pabrik read-only. Yang sudah sama dilewati, jadi patch ini aman
	dijalankan berulang.

	Untuk sebagian dokumen saja:

	    from sth.patches.isi_unit_pabrik_spb import execute
	    execute(["SPB-00123", "SPB-00124"])
	"""
	baris = _baris_beda(names)

	if not baris:
		print("Unit pabrik SPB: tidak ada baris yang perlu diisi")
		return

	for b in baris:
		frappe.db.set_value("Surat Pengantar Buah", b.name, "unit_pabrik", b.unit_timbangan)

	frappe.db.commit()

	_cetak_ringkasan(baris)


def _baris_beda(names):
	"""SPB yang unit pabriknya berbeda dari unit timbangan yang menimbangnya."""
	if isinstance(names, str):
		names = [n.strip() for n in names.split(",")]

	names = [n for n in (names or []) if n]

	syarat = ""
	nilai = {}

	if names:
		syarat = "AND spb.name IN %(names)s"
		nilai["names"] = tuple(names)

	return frappe.db.sql("""
		SELECT spb.name, spb.unit_pabrik AS lama, t.unit AS unit_timbangan
		FROM `tabSurat Pengantar Buah` spb
		INNER JOIN `tabTimbangan` t ON t.spb = spb.name AND t.docstatus = 1
		WHERE spb.docstatus < 2
			AND IFNULL(t.unit, '') != ''
			AND IFNULL(spb.unit_pabrik, '') != t.unit
			{syarat}
		ORDER BY spb.name, t.name
	""".format(syarat=syarat), nilai, as_dict=True)


def _cetak_ringkasan(baris):
	rekap = {}

	for b in baris:
		kunci = (b.lama or "", b.unit_timbangan)
		rekap[kunci] = rekap.get(kunci, 0) + 1

	print(f"Unit pabrik SPB: {len(baris)} dokumen diisi dari unit timbangannya")

	for (lama, baru), jumlah in sorted(rekap.items(), key=lambda pasangan: -pasangan[1]):
		print(f"  {lama or '(kosong)'} -> {baru}: {jumlah} dokumen")

	for b in baris[:BATAS_RINCIAN]:
		print(f"  {b.name}: {b.lama or '(kosong)'} -> {b.unit_timbangan}")

	if len(baris) > BATAS_RINCIAN:
		print(f"  ... dan {len(baris) - BATAS_RINCIAN} dokumen lain")
