import frappe

from frappe.custom.doctype.custom_field.custom_field import create_custom_field

DOCTYPE = "Stock Entry Detail"
FIELD_TIPE = "custom_tipe_asset"
FIELD_ASSET = "custom_alat_berat_dan_kendaraan"

# Sama persis dengan Select tipe_asset di Pengeluaran Barang Item, karena nilai
# di field ini disalin apa adanya dari sana lewat create_ste().
TIPE_ASSET_OPTIONS = "Asset\nAlat Berat Dan Kendaraan\nMill Machine"

# Urutan penebakan saat backfill: dulu fieldnya Link ke Alat Berat Dan
# Kendaraan, jadi itu yang paling mungkin benar kalau namanya ada di dua tempat.
URUTAN_TEBAKAN = ("Alat Berat Dan Kendaraan", "Asset", "Mill Machine")


def execute():
	"""custom_alat_berat_dan_kendaraan di Stock Entry Detail jadi Dynamic Link.

	Sumbernya, kendaraan di Pengeluaran Barang Item, sudah Dynamic Link yang
	doctype tujuannya ditentukan tipe_asset, jadi Asset dan Mill Machine ikut
	lewat sini. Selama field tujuannya masih Link ke Alat Berat Dan Kendaraan,
	nilai dari dua tipe lain tersimpan sebagai link yang menggantung.
	"""
	buat_field_tipe_asset()
	ubah_jadi_dynamic_link()
	backfill_tipe_asset()


def buat_field_tipe_asset():
	if frappe.db.exists("Custom Field", {"dt": DOCTYPE, "fieldname": FIELD_TIPE}):
		return

	# Field tipe ditaruh tepat sebelum field asset-nya: posisi lama field asset
	# dipakai yang baru, lalu field asset digeser ke belakangnya di bawah.
	insert_after = frappe.db.get_value(
		"Custom Field", {"dt": DOCTYPE, "fieldname": FIELD_ASSET}, "insert_after"
	)

	create_custom_field(DOCTYPE, {
		"fieldname": FIELD_TIPE,
		"label": "Tipe Asset",
		"fieldtype": "Select",
		"options": TIPE_ASSET_OPTIONS,
		"insert_after": insert_after or "cost_center",
	}, ignore_validate=True)


def ubah_jadi_dynamic_link():
	name = frappe.db.get_value("Custom Field", {"dt": DOCTYPE, "fieldname": FIELD_ASSET})

	if not name:
		create_custom_field(DOCTYPE, {
			"fieldname": FIELD_ASSET,
			"label": "Alat Berat Dan Kendaraan",
			"fieldtype": "Dynamic Link",
			"options": FIELD_TIPE,
			"insert_after": FIELD_TIPE,
		}, ignore_validate=True)
		return

	doc = frappe.get_doc("Custom Field", name)

	if doc.fieldtype == "Dynamic Link" and doc.options == FIELD_TIPE:
		return

	doc.fieldtype = "Dynamic Link"
	doc.options = FIELD_TIPE

	# Kalau field tipe sudah ada dari sebelumnya dan justru bersandar pada field
	# ini, jangan dibalik — insert_after yang saling menunjuk bikin form gagal
	# dirender. Urutan cuma soal tampilan, jadi biarkan apa adanya.
	tipe_insert_after = frappe.db.get_value(
		"Custom Field", {"dt": DOCTYPE, "fieldname": FIELD_TIPE}, "insert_after"
	)
	if tipe_insert_after != FIELD_ASSET:
		doc.insert_after = FIELD_TIPE

	doc.save(ignore_permissions=True)


def backfill_tipe_asset():
	"""Baris lama belum punya tipe, padahal Dynamic Link tanpa tipe tidak bisa dibuka.

	Tipenya ditebak dari doctype mana yang benar-benar punya nama itu, bukan
	diseragamkan ke Alat Berat Dan Kendaraan, karena nilai bertipe Asset dan
	Mill Machine sudah sempat masuk lewat create_ste() sebelum patch ini.
	"""
	if not (
		frappe.db.has_column(DOCTYPE, FIELD_TIPE)
		and frappe.db.has_column(DOCTYPE, FIELD_ASSET)
	):
		return

	sebelum = _hitung_belum_bertipe()

	for doctype in URUTAN_TEBAKAN:
		if not frappe.db.exists("DocType", doctype):
			continue

		frappe.db.sql(
			"""
			UPDATE `tab{sed}` sed
			SET sed.`{field_tipe}` = %s
			WHERE IFNULL(sed.`{field_asset}`, '') != ''
				AND IFNULL(sed.`{field_tipe}`, '') = ''
				AND EXISTS (
					SELECT 1 FROM `tab{target}` t
					WHERE t.name = sed.`{field_asset}`
				)
			""".format(
				sed=DOCTYPE,
				field_tipe=FIELD_TIPE,
				field_asset=FIELD_ASSET,
				target=doctype,
			),
			(doctype,),
		)

	tertinggal = _hitung_belum_bertipe()

	print(
		"Tipe asset terisi pada {0} baris Stock Entry Detail.".format(sebelum - tertinggal)
	)

	if tertinggal:
		# Namanya tidak ketemu di ketiga doctype: master-nya sudah dihapus atau
		# namanya berubah. Dibiarkan kosong supaya ketahuan, bukan ditebak asal.
		print(
			"{0} baris masih kosong tipenya karena nama asset-nya tidak ada di "
			"Alat Berat Dan Kendaraan, Asset, maupun Mill Machine. "
			"Perlu dicek manual.".format(tertinggal)
		)


def _hitung_belum_bertipe():
	return frappe.db.sql(
		"""
		SELECT COUNT(*)
		FROM `tab{sed}`
		WHERE IFNULL(`{field_asset}`, '') != ''
			AND IFNULL(`{field_tipe}`, '') = ''
		""".format(sed=DOCTYPE, field_tipe=FIELD_TIPE, field_asset=FIELD_ASSET)
	)[0][0]
