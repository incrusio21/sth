import frappe

from sth.accounting_sth.doctype.cogs_mill_dan_kebun.cogs_mill_dan_kebun import KEPALA_AKUN_MILL

FIELDNAME = "sth_accounting_settings_cogs_sumber_biaya"
KELOMPOK = "Mill"


def execute():
	"""Isi Biaya Mill di COGS dengan kepala akun 63 dan 72 tiap company.

	Biaya Mill di COGS Mill dan Kebun adalah total kepala akun 63 (Proses
	Pabrik) dan 72 (Biaya Tidak Langsung). Selama ini tabel COGS Sumber Biaya
	harus diisi tangan satu per satu, padahal kepala akunnya sama untuk semua
	company dan cuma abbr di belakang namanya yang berbeda.

	Yang diisi cuma company yang punya Unit bertanda mill. Company tanpa pabrik
	tidak akan pernah punya dokumen COGS, jadi barisnya tidak ada gunanya.

	Baris yang sudah ada tidak disentuh: kalau akunnya sudah terdaftar untuk
	company itu, apa pun kelompoknya, patch ini melewatinya supaya penyetelan
	tangan yang sudah dilakukan tidak tertimpa.
	"""
	settings = frappe.get_single("STH Accounting Settings")

	sudah = {
		(row.company, row.akun)
		for row in settings.get(FIELDNAME) or []
	}

	# Company tanpa pabrik tidak akan pernah punya dokumen COGS, jadi barisnya
	# cuma jadi keramaian di tabel setelan yang dibaca orang.
	company_mill = set(frappe.get_all("Unit", filters={"mill": 1}, pluck="company"))
	if not company_mill:
		print("Tidak ada Unit bertanda mill, dilewati.")
		return

	akun = frappe.get_all(
		"Account",
		filters={
			"account_number": ("in", KEPALA_AKUN_MILL),
			"is_group": 1,
			"company": ("in", list(company_mill)),
		},
		fields=["name", "company"],
		order_by="company asc, account_number asc",
	)

	if not akun:
		print("Tidak ada akun grup bernomor {0} di company bermill, dilewati.".format(
			", ".join(KEPALA_AKUN_MILL)
		))
		return

	ditambah = 0
	for row in akun:
		if (row.company, row.name) in sudah:
			continue

		settings.append(FIELDNAME, {
			"company": row.company,
			"kelompok": KELOMPOK,
			"akun": row.name,
		})
		ditambah += 1

	if not ditambah:
		print("Sumber Biaya Mill sudah lengkap, tidak ada yang ditambah.")
		return

	settings.flags.ignore_permissions = True
	settings.save()

	print("{0} baris Sumber Biaya Mill ditambahkan.".format(ditambah))
