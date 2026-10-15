import frappe

# Akun difference Stock Entry Data TBS, Sounding CPO dan Sounding PK yang
# sudah diketahui. Company lain diisi sendiri lewat Mill Settings.
AKUN_DIFFERENCE = {
	"PT. TRIMITRA LESTARI": "6411400",
}


def execute():
	"""Isi tabel Akun Difference Mill Settings dari AKUN_DIFFERENCE.

	Company yang tidak ada di site ini, atau yang akunnya tidak ditemukan,
	dilewati. Baris yang sudah ada tidak ditimpa.
	"""
	settings = frappe.get_single("Mill Settings")
	sudah = {row.company for row in settings.akun_difference}
	berubah = False

	for company, nomor in AKUN_DIFFERENCE.items():
		if company in sudah or not frappe.db.exists("Company", company):
			continue

		akun = frappe.db.get_value(
			"Account", {"company": company, "account_number": nomor, "is_group": 0}, "name"
		)
		if not akun:
			print(f"Akun {nomor} tidak ditemukan di {company}, dilewati.")
			continue

		settings.append("akun_difference", {"company": company, "account": akun})
		berubah = True

	if berubah:
		settings.flags.ignore_mandatory = True
		settings.save(ignore_permissions=True)
