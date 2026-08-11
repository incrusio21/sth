
import frappe
from frappe import _
from frappe.utils import flt

# Akun penjualan asset. Dicari lewat nomor akun, bukan nama, karena nama akun
# selalu berakhiran singkatan company (mis. "9190201 - ... - TML").
AKUN_DISPOSAL = "9190201"

# Piutang untuk penjualan di luar penjualan barang biasa
AKUN_PIUTANG_LAIN = "1131004"

# Jenis Penagihan yang piutangnya tidak mengikuti default Customer/Company
JENIS_PENAGIHAN_PIUTANG_LAIN = ("Others", "Disposal")


def set_debit_to(self, method=None):
	"""Piutang untuk Jenis Penagihan Others dan Disposal.

	Dipasang di before_validate supaya validate_debit_to_acc bawaan ERPNext ikut
	memeriksa akun ini — kalau disetel setelah validate, party_account_currency
	dan pemeriksaan tipe akunnya masih memakai akun yang lama.
	"""
	if self.jenis_penagihan not in JENIS_PENAGIHAN_PIUTANG_LAIN:
		return

	self.debit_to = cari_akun(self.company, AKUN_PIUTANG_LAIN, _("piutang penjualan {0}").format(self.jenis_penagihan))


def cari_akun(company, account_number, keperluan):
	"""Nama dokumen Account dari nomor akunnya untuk sebuah company."""
	account = frappe.db.get_value(
		"Account",
		{
			"account_number": account_number,
			"company": company,
			"is_group": 0,
		},
		"name"
	)

	if not account:
		frappe.throw(
			_("Akun dengan nomor {0} tidak ditemukan di company {1}. "
			  "Akun tersebut dibutuhkan sebagai {2}.").format(
				frappe.bold(account_number), frappe.bold(company), keperluan
			)
		)

	return account


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
	account = cari_akun(doc.company, AKUN_DISPOSAL, _("akun Sales Invoice penjualan asset"))

	for item in doc.items:
		item.expense_account = account
		item.income_account = account


def matikan_pembulatan(doc):
	"""Jurnal penjualan asset harus persis dua baris: piutang lawan akun penjualan.

	Pembulatan grand_total memunculkan baris ketiga ke akun Round Off company.
	Selain menyalakan disable_rounded_total, angka pembulatan yang terlanjur
	dihitung sisi client ikut dinolkan — validate ERPNext tidak dipanggil di
	override Sales Invoice, jadi tidak ada yang menghitung ulang field ini di
	server. Tanpa dinolkan, make_gle_for_rounding_adjustment() tetap membaca
	rounding_adjustment yang lama dan barisnya tetap terbentuk.
	"""
	doc.disable_rounded_total = 1
	doc.rounding_adjustment = 0
	doc.base_rounding_adjustment = 0
	doc.rounded_total = 0
	doc.base_rounded_total = 0


def validate_penjualan_asset(self, method=None):
	"""Penjualan asset hanya boleh sebanyak qty yang sudah discrap, dan jurnalnya
	cuma piutang lawan akun penjualan asset di baris item.

	Nilai buku asetnya sudah dihapus waktu discrap lewat Asset Scrap Request, jadi
	jurnal pelepasan bawaan ERPNext — akumulasi penyusutan, akun aset tetap, dan
	laba/rugi pelepasan — tidak boleh terbentuk lagi dari invoice ini. Caranya
	dengan melepas penanda is_fixed_asset di barisnya; link Asset-nya tetap
	disimpan untuk jejak dan perhitungan sisa qty yang boleh dijual."""
	if self.jenis_penagihan != "Disposal":
		return

	matikan_pembulatan(self)

	from sth.overrides.asset import sisa_qty_scrap

	for item in self.items:
		if not item.asset:
			frappe.throw(
				_("Baris {0}: Asset yang dijual wajib dipilih untuk Sales Invoice Disposal.").format(
					item.idx
				)
			)

		sisa = sisa_qty_scrap(item.asset, kecuali_sales_invoice=self.name)

		if flt(item.qty) > sisa:
			frappe.throw(
				_("Baris {0}: Asset {1} yang sudah discrap dan belum terjual tinggal {2}, "
				  "tidak bisa dijual sebanyak {3}.").format(
					item.idx, frappe.bold(item.asset), sisa, flt(item.qty)
				),
				title=_("Melebihi Qty Discrap")
			)

		item.is_fixed_asset = 0


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
