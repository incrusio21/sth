
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


@frappe.whitelist()
def get_item_default_accounts(item_code, company):
	"""Income dan expense account dari Item Default untuk company tertentu.

	Balikan selalu punya kedua key, isinya None kalau belum diisi — dipakai sisi
	client untuk memperingatkan sejak item dipilih, bukan menunggu save ditolak.
	"""
	default = frappe.db.get_value(
		"Item Default",
		{
			"parent": item_code,
			"parenttype": "Item",
			"company": company,
		},
		["expense_account", "income_account"],
		as_dict=True
	) or frappe._dict()

	return {
		"income_account": default.income_account,
		"expense_account": default.expense_account,
	}


def set_account_from_item_default(doc):
	"""Ambil expense dan income account dari Item Default milik company dokumen ini.

	Item yang belum punya default ditolak, tidak dibiarkan memakai nilai lama:
	ERPNext sudah mengisi kedua field itu dari default company lewat rantai
	Item Default -> Item Group -> Company, jadi membiarkannya berarti jurnalnya
	diam-diam jatuh ke akun default company.
	"""
	for item in doc.items:
		if not item.item_code:
			continue

		default = get_item_default_accounts(item.item_code, doc.company)

		kosong = [
			label for label, akun in (
				("Income Account", default["income_account"]),
				("Expense Account", default["expense_account"]),
			) if not akun
		]

		if kosong:
			frappe.throw(
				_("Baris {0}: Item {1} belum punya {2} di Item Defaults untuk company {3}. "
				  "Lengkapi dulu di master Item.").format(
					item.idx,
					frappe.bold(item.item_code),
					frappe.bold(" dan ".join(kosong)),
					frappe.bold(doc.company)
				),
				title=_("Item Default Belum Lengkap")
			)

		item.expense_account = default["expense_account"]
		item.income_account = default["income_account"]
