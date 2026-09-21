import frappe

# Batas rincian yang dicetak, supaya output bench tidak kebanjiran kalau yang
# perlu diisi ternyata banyak.
BATAS_RINCIAN = 20


def execute(timbangan_names=None):
	"""Isi kebun di Timbangan dari unit SPB-nya.

	Kebun di Timbangan di-fetch dari ticket_number.unit, dan unit Security Check
	Point ikut lokasi pos penjagaannya — pos itu berdiri di pabrik, jadi yang
	tersimpan di sana kode pabrik (TPRM, ASRM, ABAM), bukan kebun yang memanen.
	Kebun pengirimnya cuma diketahui SPB.

	Dokumen baru sudah tertutup dua jalur: Timbangan.set_kebun_dari_spb waktu
	timbangannya disimpan, dan _resync_kebun_timbangan di Surat Pengantar Buah
	waktu unit SPB-nya dikoreksi kiriman API. Yang tersisa dokumen lama, dan itu
	yang diurus di sini.

	Field `unit` tidak disentuh: itu pabrik yang menimbang, dan COGS Mill dan
	Kebun, laporan penerimaan TBS mill, serta hitungan sortasi menyaring dengan
	arti itu.

	Ditulis lewat db.set_value karena hampir semua timbangannya sudah submit, dan
	kebun read-only ber-fetch_from sehingga menyimpan lewat dokumen malah
	mengembalikannya ke unit pos. `modified` sengaja ikut naik supaya sinkronisasi
	inkremental EPCS lewat modified_after melihat barisnya lagi.

	Yang sudah dibatalkan dilewati, begitu juga yang kebunnya sudah sama — patch
	ini aman dijalankan berulang.

	Untuk sebagian dokumen saja:

	    from sth.patches.isi_kebun_timbangan_dari_spb import execute
	    execute(["TBG-10986", "TBG-10987"])
	"""
	baris = _baris_beda(timbangan_names)

	if not baris:
		print("Kebun Timbangan: tidak ada baris yang perlu diisi")
		return

	for b in baris:
		frappe.db.set_value("Timbangan", b.name, "kebun", b.unit_spb)

	_cetak_ringkasan(baris)


def _baris_beda(timbangan_names):
	"""Timbangan yang kebunnya berbeda dari unit SPB yang ditunjuknya."""
	if isinstance(timbangan_names, str):
		timbangan_names = [n.strip() for n in timbangan_names.split(",")]

	names = [n for n in (timbangan_names or []) if n]

	syarat = ""
	nilai = {}

	if names:
		syarat = "AND t.name IN %(names)s"
		nilai["names"] = tuple(names)

	return frappe.db.sql("""
		SELECT t.name, t.kebun AS kebun_lama, spb.unit AS unit_spb
		FROM `tabTimbangan` t
		INNER JOIN `tabSurat Pengantar Buah` spb ON spb.name = t.spb
		WHERE t.docstatus < 2
			AND IFNULL(spb.unit, '') != ''
			AND IFNULL(t.kebun, '') != spb.unit
			{syarat}
		ORDER BY t.name
	""".format(syarat=syarat), nilai, as_dict=True)


def _cetak_ringkasan(baris):
	rekap = {}

	for b in baris:
		kunci = (b.kebun_lama or "", b.unit_spb)
		rekap[kunci] = rekap.get(kunci, 0) + 1

	print(f"Kebun Timbangan: {len(baris)} dokumen diisi dari unit SPB-nya")

	for (lama, baru), jumlah in sorted(rekap.items(), key=lambda pasangan: -pasangan[1]):
		print(f"  {lama or '(kosong)'} -> {baru}: {jumlah} dokumen")

	for b in baris[:BATAS_RINCIAN]:
		print(f"  {b.name}: {b.kebun_lama or '(kosong)'} -> {b.unit_spb}")

	if len(baris) > BATAS_RINCIAN:
		print(f"  ... dan {len(baris) - BATAS_RINCIAN} dokumen lain")
