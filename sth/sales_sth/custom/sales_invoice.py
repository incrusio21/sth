
import frappe
from frappe import _

# Akun beban untuk penjualan asset. Dicari lewat nomor akun, bukan nama, karena
# nama akun selalu berakhiran singkatan company (mis. "9190201 - ... - TML").
AKUN_BEBAN_DISPOSAL = "9190201"

def validate_expense_account(self, method):
	if self.jenis_penagihan == "Uang Muka":
		default_account = frappe.db.get_value(
			"Company",
			self.company,
			"default_uang_muka_penjualan_account"
		)

		if default_account:
			for item in self.items:
				item.income_account = default_account
	elif self.jenis_penagihan == "Disposal":
		set_expense_account_disposal(self)
	elif self.jenis_penagihan == "Others":
		set_expense_account_from_item_default(self)


def set_expense_account_disposal(doc):
	"""Paksa expense account item ke akun beban penjualan asset.

	Dipasang di sini, bukan hanya di sisi client, supaya invoice yang dibuat lewat
	tombol Sell di Asset atau lewat API tetap kena akun yang sama.
	"""
	account = frappe.db.get_value(
		"Account",
		{
			"account_number": AKUN_BEBAN_DISPOSAL,
			"company": doc.company,
			"is_group": 0,
		},
		"name"
	)

	if not account:
		frappe.throw(
			_("Akun dengan nomor {0} tidak ditemukan di company {1}. "
			  "Akun tersebut dibutuhkan sebagai Expense Account penjualan asset.").format(
				frappe.bold(AKUN_BEBAN_DISPOSAL), frappe.bold(doc.company)
			)
		)

	for item in doc.items:
		item.expense_account = account


def set_expense_account_from_item_default(doc):
	"""Ambil expense account dari Item Default milik company dokumen ini.

	Baris yang itemnya tidak punya default dibiarkan apa adanya — nilai yang
	sudah diisi ERPNext (default company atau isian manual) tetap dipakai.
	"""
	for item in doc.items:
		if not item.item_code:
			continue

		account = frappe.db.get_value(
			"Item Default",
			{
				"parent": item.item_code,
				"parenttype": "Item",
				"company": doc.company,
			},
			"expense_account"
		)

		if account:
			item.expense_account = account
