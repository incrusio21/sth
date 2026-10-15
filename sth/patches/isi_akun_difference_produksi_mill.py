import frappe

# Akun difference TBS yang sudah diketahui, per company. CPO dan Palm Kernel
# diisi sendiri lewat STH Accounting Settings.
AKUN_DIFFERENCE_TBS = {
	"PT. TRIMITRA LESTARI": "6411400",
}


def execute():
	"""Isi kolom Difference TBS tabel Akun Difference Produksi Mill di STH
	Accounting Settings dari AKUN_DIFFERENCE_TBS.

	Company yang tidak ada di site ini, atau yang akunnya tidak ditemukan,
	dilewati. Kolom yang sudah terisi tidak ditimpa.
	"""
	settings = frappe.get_single("STH Accounting Settings")
	berubah = False

	for company, nomor in AKUN_DIFFERENCE_TBS.items():
		if not frappe.db.exists("Company", company):
			continue

		row = next((d for d in settings.sth_accounting_settings_akun_difference if d.company == company), None)
		if row and row.akun_difference_tbs:
			continue

		akun = frappe.db.get_value(
			"Account", {"company": company, "account_number": nomor, "is_group": 0}, "name"
		)
		if not akun:
			print(f"Akun {nomor} tidak ditemukan di {company}, dilewati.")
			continue

		if not row:
			row = settings.append("sth_accounting_settings_akun_difference", {"company": company})
		row.akun_difference_tbs = akun
		berubah = True

	if berubah:
		settings.flags.ignore_mandatory = True
		settings.save(ignore_permissions=True)
