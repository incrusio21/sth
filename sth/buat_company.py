# Buat company baru dengan bagan akun dan akun default meniru TML.
#
# bench --site <site> execute sth.buat_company.execute

import frappe

from sth.put_company import ACCOUNT_FIELDS, SOURCE_COMPANY, fix_company

# Company yang dibuat, beserta singkatannya. Singkatan dipakai sebagai akhiran
# nama akun ("Sales - STA"), jadi tidak boleh sama dengan company yang sudah ada.
COMPANY_BARU = {
	"PT Sumber Tani Agung": "STA",
	"PT Sumber Pelita Jaya": "SPJ",
}


def execute():
	"""Buat company di COMPANY_BARU, bagan akun dan akun defaultnya mengikuti TML.

	Dua langkah: company dibuat dengan create_chart_of_accounts_based_on
	"Existing Company" supaya ERPNext menyalin seluruh bagan akun TML, lalu akun
	default di Company-nya sendiri (default_bank_account, default_expense_account,
	dan seterusnya) disamakan lewat fix_company dari sth.put_company - akun yang
	sama, cuma akhiran singkatannya yang ikut company baru.

	Aman dijalankan ulang: company yang sudah ada tidak dibuat ulang, dan
	fix_company cuma menyentuh field yang nilainya belum benar. Tiap company
	di-commit begitu selesai, jadi kalau ada yang gagal yang sudah beres tidak
	ikut hangus.
	"""
	if not frappe.db.exists("Company", SOURCE_COMPANY):
		print("Company sumber '{0}' tidak ada, dibatalkan.".format(SOURCE_COMPANY))
		return

	sumber = frappe.get_doc("Company", SOURCE_COMPANY)
	akun_sumber = {field: sumber.get(field) for field in ACCOUNT_FIELDS}

	print("Menyalin dari {0} (singkatan {1}).".format(SOURCE_COMPANY, sumber.abbr))

	for nama, singkatan in COMPANY_BARU.items():
		if not buat_company(nama, singkatan, sumber):
			continue

		fix_company(nama, sumber.abbr, akun_sumber)
		frappe.db.commit()

	print("Selesai.")


def buat_company(nama, singkatan, sumber):
	"""Buat satu Company baru yang bagan akunnya disalin dari company sumber.

	Mengembalikan False kalau company itu tidak bisa dilanjutkan ke penyamaan akun
	default - singkatannya bentrok, jadi akunnya belum tentu milik company ini.

	Mata uang dan negaranya ikut company sumber, bukan ditulis tetap di sini,
	supaya bagan akun salinannya tidak beda mata uang dengan induknya.
	"""
	if frappe.db.exists("Company", nama):
		print("{0} sudah ada, bagan akunnya tidak dibuat ulang.".format(nama))
		return True

	pemakai_singkatan = frappe.db.get_value("Company", {"abbr": singkatan}, "name")
	if pemakai_singkatan:
		print("Singkatan {0} sudah dipakai {1}, {2} dilewati.".format(
			singkatan, pemakai_singkatan, nama
		))
		return False

	doc = frappe.get_doc({
		"doctype": "Company",
		"company_name": nama,
		"abbr": singkatan,
		"default_currency": sumber.default_currency,
		"country": sumber.country,
		"create_chart_of_accounts_based_on": "Existing Company",
		"existing_company": sumber.name,
	})

	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	print("{0} dibuat, {1} akun disalin dari {2}.".format(
		nama, frappe.db.count("Account", {"company": nama}), sumber.name
	))

	return True
