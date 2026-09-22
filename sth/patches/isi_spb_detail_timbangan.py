import frappe

from sth.mill.doctype.timbangan.timbangan import sinkronkan_spb_detail

# Batas rincian yang dicetak, supaya output bench tidak kebanjiran kalau yang
# perlu diisi ternyata banyak.
BATAS_RINCIAN = 20


def execute(timbangan_names=None):
	"""Isi rincian blok di Timbangan dari SPB-nya untuk dokumen lama.

	Tabel spb_detail selama ini cuma diisi trigger `spb` di form Timbangan, jadi
	tiket yang datang lewat API EPCS rinciannya kosong. Tiket seperti itu hilang
	sama sekali dari Perhitungan KUD: netto dicatat sekali di kepala tiket dan
	baris-baris inilah yang membaginya ke tahun tanam, jadi tanpa baris tidak ada
	yang bisa ditempeli harga — bukan salah alamat, tapi tidak terhitung.

	Dokumen baru sudah tertutup dua jalur: Timbangan.isi_spb_detail waktu
	tiketnya disimpan, dan _resync_spb_detail_timbangan di Surat Pengantar Buah
	waktu rincian SPB-nya dikoreksi kiriman API. Yang tersisa dokumen lama, dan
	itu yang diurus di sini.

	Yang sudah punya rincian tidak disentuh sama sekali, termasuk yang isinya
	sudah tidak sama lagi dengan SPB-nya: menulis ulang isian lama bukan urusan
	patch ini, dan resync di atas yang akan membereskannya begitu kiriman
	berikutnya datang.

	Restan tidak ikut, sama seperti get_spb_detail yang dipakai form: yang masuk
	`jumlah_janjang` hanya qty panen.

	Yang sudah dibatalkan dilewati, begitu juga yang SPB-nya sendiri belum punya
	rincian — patch ini aman dijalankan berulang.

	Untuk sebagian dokumen saja:

	    from sth.patches.isi_spb_detail_timbangan import execute
	    execute(["TBG-10986", "TBG-10987"])
	"""
	baris = _tiket_tanpa_rincian(timbangan_names)

	if not baris:
		print("Rincian blok Timbangan: tidak ada tiket yang perlu diisi")
		return

	terisi = []

	for b in baris:
		if sinkronkan_spb_detail(b.name, b.docstatus, b.spb):
			terisi.append(b)

	frappe.db.commit()

	_cetak_ringkasan(baris, terisi)


def _tiket_tanpa_rincian(timbangan_names):
	"""Timbangan ber-SPB yang tabel rinciannya masih kosong."""
	if isinstance(timbangan_names, str):
		timbangan_names = [n.strip() for n in timbangan_names.split(",")]

	names = [n for n in (timbangan_names or []) if n]

	syarat = ""
	nilai = {}

	if names:
		syarat = "AND t.name IN %(names)s"
		nilai["names"] = tuple(names)

	return frappe.db.sql("""
		SELECT t.name, t.docstatus, t.spb, t.kebun, t.netto_2
		FROM `tabTimbangan` t
		LEFT JOIN `tabTimbangan SPB Detail` d
			ON d.parent = t.name AND d.parenttype = 'Timbangan'
		WHERE t.docstatus < 2
			AND IFNULL(t.spb, '') != ''
			AND d.name IS NULL
			{syarat}
		ORDER BY t.name
	""".format(syarat=syarat), nilai, as_dict=True)


def _cetak_ringkasan(baris, terisi):
	rekap = {}

	for b in terisi:
		kebun = b.kebun or "(kosong)"
		jumlah, netto = rekap.get(kebun, (0, 0.0))
		rekap[kebun] = (jumlah + 1, netto + (b.netto_2 or 0))

	print("Rincian blok Timbangan: {} dari {} tiket terisi dari SPB-nya".format(
		len(terisi), len(baris)
	))

	for kebun, (jumlah, netto) in sorted(rekap.items(), key=lambda pasangan: -pasangan[1][0]):
		print(f"  {kebun}: {jumlah} tiket, netto {netto:,.0f} kg")

	for b in terisi[:BATAS_RINCIAN]:
		print(f"  {b.name}: {b.spb}")

	if len(terisi) > BATAS_RINCIAN:
		print(f"  ... dan {len(terisi) - BATAS_RINCIAN} tiket lain")

	lewat = len(baris) - len(terisi)
	if lewat:
		print(f"  {lewat} tiket dilewati: SPB-nya sendiri belum punya rincian blok")
