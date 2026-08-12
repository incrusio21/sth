import frappe

DOCTYPE = "Buku Kerja Mandor Perawatan"
TABEL = "tabBuku Kerja Mandor Perawatan"

# Tabel arsip sengaja tidak diawali "tab": di luar jangkauan ORM dan migrate
# frappe, jadi tidak pernah ikut disinkronkan atau dianggap doctype. Isinya
# salinan baris apa adanya, kolom demi kolom.
ARSIP = "arsip_buku_kerja_mandor_perawatan"

# (tabel asal, tabel arsip, parentfield) untuk tiap tabel anak BKM Perawatan.
#
# Dokumen batal sisa penggabungan memang sudah kosong — baris hasil kerja dan
# materialnya sudah pindah ke dokumen penampung. Tapi dokumen yang dibatalkan
# orang lewat cara biasa tetap memegang baris anaknya, dan membuang induknya
# tanpa membawa serta baris itu cuma meninggalkan baris yatim di database.
ANAK = (
	("tabDetail BKM Hasil Kerja Perawatan", "arsip_detail_bkm_hasil_kerja_perawatan", "hasil_kerja"),
	("tabDetail BKM Material", "arsip_detail_bkm_material", "material"),
)


def execute():
	"""Pindahkan BKM Perawatan yang sudah dibatalkan ke tabel arsip.

	Dokumen batal menumpuk di daftar BKM Perawatan tanpa memberi keterangan apa
	pun — sebagian besar sisa penggabungan dokumen kembar, yang isinya sudah
	pindah ke dokumen penampung dan tinggal cangkang bernomor.

	Barisnya disalin utuh, kolom demi kolom, lalu dihapus dari tabel utama. Karena
	salinannya lengkap, pemindahan ini bisa dibalik dengan INSERT balik dari tabel
	arsip — lihat keterangan di akhir modul.

	GL Entry dan Employee Payment Log sengaja tidak disentuh. Yang tersisa milik
	dokumen batal semuanya sudah is_cancelled, jadi tidak masuk laporan dan tidak
	mengubah saldo; membuangnya berarti menghapus jejak akuntansi tanpa alasan.
	Jumlahnya dicetak supaya kelihatan kalau ternyata ada yang belum bersih.
	"""
	nama = frappe.db.sql_list(f"SELECT name FROM `{TABEL}` WHERE docstatus = 2")
	if not nama:
		print("BKM Perawatan batal: tidak ada yang perlu diarsipkan")
		return

	_siapkan_tabel_arsip()

	# dihitung sebelum apa pun dipindah, supaya angkanya menggambarkan keadaan awal
	laporan = _hitung_keadaan()

	# disetel sebelum disalin supaya arsipnya menyimpan state yang benar. Dokumen
	# batal sering meninggalkan workflow_state di state terakhir sebelum dibatalkan,
	# dan di arsip nilai itu cuma menyesatkan.
	if frappe.db.has_column(DOCTYPE, "workflow_state"):
		frappe.db.sql(f"UPDATE `{TABEL}` SET workflow_state = 'Cancelled' WHERE docstatus = 2")

	_salin(TABEL, ARSIP, "docstatus = 2")

	for tabel_asal, tabel_arsip, parentfield in ANAK:
		_salin(
			tabel_asal,
			tabel_arsip,
			f"parenttype = '{DOCTYPE}' AND parentfield = '{parentfield}' "
			f"AND parent IN (SELECT name FROM `{TABEL}` WHERE docstatus = 2)",
		)

	# anak dulu, induknya belakangan: penyaring baris anak ikut membaca tabel induk
	for tabel_asal, _, parentfield in ANAK:
		frappe.db.sql(
			f"""
			DELETE FROM `{tabel_asal}`
			WHERE parenttype = %s AND parentfield = %s
				AND parent IN (SELECT name FROM `{TABEL}` WHERE docstatus = 2)
			""",
			(DOCTYPE, parentfield),
		)

	frappe.db.sql(f"DELETE FROM `{TABEL}` WHERE docstatus = 2")
	frappe.db.commit()

	_cetak_laporan(len(nama), laporan)


def _siapkan_tabel_arsip():
	frappe.db.sql(f"CREATE TABLE IF NOT EXISTS `{ARSIP}` LIKE `{TABEL}`")

	for tabel_asal, tabel_arsip, _ in ANAK:
		frappe.db.sql(f"CREATE TABLE IF NOT EXISTS `{tabel_arsip}` LIKE `{tabel_asal}`")


def _salin(tabel_asal, tabel_arsip, kondisi):
	"""Salin baris yang cocok ke tabel arsip, kolom demi kolom.

	Kolomnya disebut satu per satu, bukan SELECT *, supaya tetap benar kalau
	doctype-nya bertambah field sesudah tabel arsip dibuat. Kolom yang cuma ada
	di salah satu sisi dilewati.

	INSERT IGNORE dipakai supaya patch yang gagal di tengah jalan bisa diulang:
	baris yang sudah terlanjur tersalin ditolak primary key dan dilewati begitu
	saja, bukan menggagalkan seluruh perintah.
	"""
	kolom_arsip = set(_kolom(tabel_arsip))
	kolom = [k for k in _kolom(tabel_asal) if k in kolom_arsip]

	if not kolom:
		frappe.throw(f"Tabel arsip `{tabel_arsip}` tidak punya kolom yang cocok dengan `{tabel_asal}`")

	daftar = ", ".join(f"`{k}`" for k in kolom)

	frappe.db.sql(
		f"INSERT IGNORE INTO `{tabel_arsip}` ({daftar}) SELECT {daftar} FROM `{tabel_asal}` WHERE {kondisi}"
	)


def _kolom(tabel):
	return frappe.db.sql_list(
		"""
		SELECT column_name FROM information_schema.columns
		WHERE table_schema = DATABASE() AND table_name = %s
		ORDER BY ordinal_position
		""",
		tabel,
	)


def _hitung_keadaan():
	"""Angka-angka yang perlu dilihat orang sesudah patch jalan."""
	batal = f"(SELECT name FROM `{TABEL}` WHERE docstatus = 2)"

	keadaan = {"anak": {}}

	for tabel_asal, _, parentfield in ANAK:
		keadaan["anak"][parentfield] = frappe.db.sql(
			f"""
			SELECT COUNT(*), COUNT(DISTINCT parent) FROM `{tabel_asal}`
			WHERE parenttype = %s AND parentfield = %s AND parent IN {batal}
			""",
			(DOCTYPE, parentfield),
		)[0]

	for doctype_acuan, kunci in (("GL Entry", "gl"), ("Employee Payment Log", "epl")):
		keadaan[kunci] = frappe.db.sql(
			f"""
			SELECT COUNT(*), COUNT(DISTINCT voucher_no) FROM `tab{doctype_acuan}`
			WHERE voucher_type = %s AND voucher_no IN {batal}
			""",
			(DOCTYPE,),
		)[0]

	return keadaan


def _cetak_laporan(jumlah, keadaan):
	print(f"BKM Perawatan batal: {jumlah} dokumen dipindah ke `{ARSIP}`")

	for parentfield, (baris, dokumen) in keadaan["anak"].items():
		if baris:
			print(f"  {parentfield}: {baris} baris dari {dokumen} dokumen ikut diarsipkan")

	for kunci, label in (("gl", "GL Entry"), ("epl", "Employee Payment Log")):
		baris, dokumen = keadaan[kunci]
		if baris:
			print(f"  {baris} {label} dari {dokumen} dokumen masih menunjuk nomor yang sudah diarsipkan")


# Mengembalikan seluruh isi arsip ke tabel utama, kalau suatu saat perlu:
#
#     INSERT INTO `tabBuku Kerja Mandor Perawatan`
#         SELECT * FROM `arsip_buku_kerja_mandor_perawatan`;
#     INSERT INTO `tabDetail BKM Hasil Kerja Perawatan`
#         SELECT * FROM `arsip_detail_bkm_hasil_kerja_perawatan`;
#     INSERT INTO `tabDetail BKM Material`
#         SELECT * FROM `arsip_detail_bkm_material`;
#
# SELECT * di sini aman selama doctype-nya belum bertambah kolom sesudah arsipnya
# dibuat. Kalau sudah, sebutkan kolomnya satu per satu seperti yang dilakukan _salin.
