import frappe

# Batas rincian yang dicetak, supaya output bench tidak kebanjiran kalau yang
# perlu diisi ternyata banyak.
BATAS_RINCIAN = 20


def execute(timbangan_names=None):
	"""Isi divisi kebun di Timbangan dari divisi SPB-nya.

	Field `divisi_kebun` baru ditambahkan, jadi semua tiket yang sudah ada masih
	kosong. Divisi pengirimnya cuma diketahui SPB — yang tersimpan di pos
	penjagaan ikut lokasi posnya, bukan kebun yang memanen.

	Dokumen baru sudah tertutup dua jalur: Timbangan.set_kebun_dan_divisi_dari_spb
	waktu tiketnya disimpan, dan _resync_kebun_timbangan di Surat Pengantar Buah
	waktu divisi SPB-nya dikoreksi kiriman API. Yang tersisa dokumen lama, dan itu
	yang diurus di sini.

	Ditulis lewat db.set_value karena hampir semua tiketnya sudah submit, dan
	divisi_kebun read-only ber-fetch_from sehingga menyimpan lewat dokumen malah
	menariknya ulang. `modified` sengaja ikut naik supaya sinkronisasi inkremental
	EPCS lewat modified_after melihat barisnya lagi.

	Yang sudah dibatalkan dilewati, begitu juga yang divisinya sudah sama — patch
	ini aman dijalankan berulang.

	Untuk sebagian dokumen saja:

	    from sth.patches.isi_divisi_kebun_timbangan import execute
	    execute(["TBG-10986", "TBG-10987"])
	"""
	baris = _baris_beda(timbangan_names)

	if not baris:
		print("Divisi kebun Timbangan: tidak ada baris yang perlu diisi")
		return

	for b in baris:
		frappe.db.set_value("Timbangan", b.name, "divisi_kebun", b.divisi_spb)

	frappe.db.commit()

	_cetak_ringkasan(baris)


def _baris_beda(timbangan_names):
	"""Timbangan yang divisi kebunnya berbeda dari divisi SPB yang ditunjuknya."""
	if isinstance(timbangan_names, str):
		timbangan_names = [n.strip() for n in timbangan_names.split(",")]

	names = [n for n in (timbangan_names or []) if n]

	syarat = ""
	nilai = {}

	if names:
		syarat = "AND t.name IN %(names)s"
		nilai["names"] = tuple(names)

	return frappe.db.sql("""
		SELECT t.name, t.divisi_kebun AS lama, spb.divisi AS divisi_spb
		FROM `tabTimbangan` t
		INNER JOIN `tabSurat Pengantar Buah` spb ON spb.name = t.spb
		WHERE t.docstatus < 2
			AND IFNULL(spb.divisi, '') != ''
			AND IFNULL(t.divisi_kebun, '') != spb.divisi
			{syarat}
		ORDER BY t.name
	""".format(syarat=syarat), nilai, as_dict=True)


def _cetak_ringkasan(baris):
	rekap = {}

	for b in baris:
		kunci = (b.lama or "", b.divisi_spb)
		rekap[kunci] = rekap.get(kunci, 0) + 1

	print(f"Divisi kebun Timbangan: {len(baris)} dokumen diisi dari divisi SPB-nya")

	for (lama, baru), jumlah in sorted(rekap.items(), key=lambda pasangan: -pasangan[1]):
		print(f"  {lama or '(kosong)'} -> {baru}: {jumlah} dokumen")

	for b in baris[:BATAS_RINCIAN]:
		print(f"  {b.name}: {b.lama or '(kosong)'} -> {b.divisi_spb}")

	if len(baris) > BATAS_RINCIAN:
		print(f"  ... dan {len(baris) - BATAS_RINCIAN} dokumen lain")
