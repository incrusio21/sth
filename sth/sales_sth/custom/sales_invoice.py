
import frappe
from frappe import _

# Akun penjualan asset. Dicari lewat nomor akun, bukan nama, karena nama akun
# selalu berakhiran singkatan company (mis. "9190201 - ... - TML").
AKUN_DISPOSAL = "9190201"

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
		set_account_disposal(self)
	elif self.jenis_penagihan == "Others":
		set_account_from_item_default(self)


def set_account_disposal(doc):
	"""Paksa expense dan income account item ke akun penjualan asset.

	Dipasang di sini, bukan hanya di sisi client, supaya invoice yang dibuat lewat
	tombol Sell di Asset atau lewat API tetap kena akun yang sama.
	"""
	account = frappe.db.get_value(
		"Account",
		{
			"account_number": AKUN_DISPOSAL,
			"company": doc.company,
			"is_group": 0,
		},
		"name"
	)

	if not account:
		frappe.throw(
			_("Akun dengan nomor {0} tidak ditemukan di company {1}. "
			  "Akun tersebut dibutuhkan untuk Sales Invoice penjualan asset.").format(
				frappe.bold(AKUN_DISPOSAL), frappe.bold(doc.company)
			)
		)

	for item in doc.items:
		item.expense_account = account
		item.income_account = account


def set_account_from_item_default(doc):
	"""Ambil expense dan income account dari Item Default milik company dokumen ini.

	Field yang itemnya tidak punya default dibiarkan apa adanya — nilai yang sudah
	diisi ERPNext (default company atau isian manual) tetap dipakai.
	"""
	for item in doc.items:
		if not item.item_code:
			continue

		default = frappe.db.get_value(
			"Item Default",
			{
				"parent": item.item_code,
				"parenttype": "Item",
				"company": doc.company,
			},
			["expense_account", "income_account"],
			as_dict=True
		)

		if not default:
			continue

		if default.expense_account:
			item.expense_account = default.expense_account

		if default.income_account:
			item.income_account = default.income_account
