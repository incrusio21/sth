import frappe

DOCTYPE = "Material Request Item"
FIELDNAME = "nama_barang"


def execute():
	"""Isi Nama Barang di Material Request Item untuk baris yang sudah ada.

	Field nama_barang baru ditambahkan (fetch_from item_code.item_name) supaya
	nama item tetap terbaca di tabel sejak item_code ditampilkan sebagai kode,
	bukan title. fetch_from hanya jalan waktu item_code dipilih atau dokumen
	disimpan, jadi baris lama - termasuk seluruh MR yang sudah submit - masih
	kosong.

	Sumbernya item_name di baris itu sendiri, bukan Item master, supaya nama
	yang tercatat sama dengan waktu MR dibuat walaupun item-nya sudah diganti
	namanya. Baris yang item_name-nya kosong baru jatuh ke Item master.

	Baris yang nama_barang-nya sudah terisi dilewati, jadi aman dijalankan
	berulang kali.
	"""
	pastikan_custom_field()

	sumber = """
		FROM `tabMaterial Request Item` mri
		LEFT JOIN `tabItem` i ON i.name = mri.item_code
		WHERE COALESCE(mri.`{0}`, '') = ''
			AND COALESCE(NULLIF(mri.item_name, ''), i.item_name, '') != ''
	""".format(FIELDNAME)

	perlu_diisi = frappe.db.sql("SELECT COUNT(*) {0}".format(sumber))[0][0]
	if not perlu_diisi:
		print("Semua Material Request Item sudah punya Nama Barang, dilewati.")
		return

	# Ditulis ulang, bukan dipakai ulang dari `sumber`: di sintaks UPDATE, SET
	# duduk di antara JOIN dan WHERE.
	frappe.db.sql(
		"""
		UPDATE `tabMaterial Request Item` mri
		LEFT JOIN `tabItem` i ON i.name = mri.item_code
		SET mri.`{0}` = COALESCE(NULLIF(mri.item_name, ''), i.item_name)
		WHERE COALESCE(mri.`{0}`, '') = ''
			AND COALESCE(NULLIF(mri.item_name, ''), i.item_name, '') != ''
		""".format(FIELDNAME)
	)

	print("{0} Material Request Item diisi Nama Barang-nya.".format(perlu_diisi))


def pastikan_custom_field():
	"""Pastikan kolom nama_barang sudah ada sebelum diisi.

	Patch post_model_sync jalan sebelum sync_customizations() milik migrate, jadi
	di site yang custom field-nya belum pernah tersinkron, kolomnya belum ada
	waktu patch ini kena giliran. Disinkronkan duluan di sini; migrate tetap
	menyinkronkan lagi setelahnya dan itu tidak masalah karena sync_customizations
	idempoten.
	"""
	from frappe.modules.utils import sync_customizations

	if frappe.get_meta(DOCTYPE).get_field(FIELDNAME):
		return

	sync_customizations(app="sth")
	frappe.clear_cache(doctype=DOCTYPE)

	# cached=False supaya tidak kena meta yang masih tersimpan di proses ini.
	if not frappe.get_meta(DOCTYPE, cached=False).get_field(FIELDNAME):
		frappe.throw("Custom field {0} gagal disinkronkan ke {1}.".format(FIELDNAME, DOCTYPE))
