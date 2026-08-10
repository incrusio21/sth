import frappe
from erpnext.assets.doctype.asset.asset import Asset
from frappe import _
from frappe.utils import (
	cint,
	flt,
	get_datetime,
	get_last_day,
	get_link_to_form,
	getdate,
	nowdate,
	today,
)

from sth.sales_sth.custom.sales_invoice import AKUN_PIUTANG_LAIN

class Asset(Asset):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from erpnext.assets.doctype.asset_finance_book.asset_finance_book import AssetFinanceBook
		from frappe.types import DF

		additional_asset_cost: DF.Currency
		amended_from: DF.Link | None
		asset_category: DF.Link | None
		asset_name: DF.Data
		asset_owner: DF.Literal["", "Company", "Supplier", "Customer"]
		asset_owner_company: DF.Link | None
		asset_quantity: DF.Int
		available_for_use_date: DF.Date | None
		booked_fixed_asset: DF.Check
		calculate_depreciation: DF.Check
		company: DF.Link
		comprehensive_insurance: DF.Data | None
		cost_center: DF.Link | None
		custodian: DF.Link | None
		customer: DF.Link | None
		default_finance_book: DF.Link | None
		department: DF.Link | None
		depr_entry_posting_status: DF.Literal["", "Successful", "Failed"]
		depreciation_method: DF.Literal["", "Straight Line", "Double Declining Balance", "Manual"]
		disposal_date: DF.Date | None
		finance_books: DF.Table[AssetFinanceBook]
		frequency_of_depreciation: DF.Int
		gross_purchase_amount: DF.Currency
		image: DF.AttachImage | None
		insurance_end_date: DF.Date | None
		insurance_start_date: DF.Date | None
		insured_value: DF.Data | None
		insurer: DF.Data | None
		is_composite_asset: DF.Check
		is_existing_asset: DF.Check
		is_fully_depreciated: DF.Check
		item_code: DF.Link
		item_name: DF.ReadOnly | None
		journal_entry_for_scrap: DF.Link | None
		location: DF.Link
		maintenance_required: DF.Check
		naming_series: DF.Literal["ACC-ASS-.YYYY.-"]
		next_depreciation_date: DF.Date | None
		opening_accumulated_depreciation: DF.Currency
		opening_number_of_booked_depreciations: DF.Int
		policy_number: DF.Data | None
		purchase_amount: DF.Currency
		purchase_date: DF.Date
		purchase_invoice: DF.Link | None
		purchase_invoice_item: DF.Data | None
		purchase_receipt: DF.Link | None
		purchase_receipt_item: DF.Data | None
		split_from: DF.Link | None
		status: DF.Literal["Draft", "Submitted", "Partially Depreciated", "Fully Depreciated", "Sold", "Scrapped", "In Maintenance", "Out of Order", "Issue", "Receipt", "Capitalized", "Work In Progress"]
		supplier: DF.Link | None
		total_asset_cost: DF.Currency
		total_number_of_depreciations: DF.Int
		value_after_depreciation: DF.Currency
	# end: auto-generated types

	def validate(self):
		super().validate()

		if self.asset_category:
			create_vra_progress = frappe.get_cached_value(
				"Asset Category",
				self.asset_category,
				"create_vra_progress"
			)

			# if create_vra_progress and not self.operator:
			# 	frappe.throw("Asset Category membuat VRA Progress. Operator wajib diisi")

	def on_submit(self):
		super().on_submit()
		self.make_gl_entry()

	def make_gl_entry(self):
		if not self.asset_category:
			return

		if self.split_from:
			# asset pecahan cuma memindahkan sebagian nilai asset asalnya, yang
			# jurnal kapitalisasinya sudah diposting waktu asset itu disubmit.
			# tanpa penjaga ini akun aset tetap kelebihan sebesar nilai pecahan
			return

		asset_category_doc = frappe.get_doc("Asset Category", self.asset_category)

		fixed_asset_account = None
		cwip_account = None

		for row in asset_category_doc.accounts:
			if row.company_name == self.company:
				fixed_asset_account = row.fixed_asset_account
				cwip_account = row.capital_work_in_progress_account
				break

		if not fixed_asset_account:
			frappe.throw(f"Fixed Asset Account tidak ditemukan untuk company {self.company} di Asset Category {self.asset_category}")

		if not cwip_account:
			frappe.throw(f"Capital Work In Progress Account tidak ditemukan untuk company {self.company} di Asset Category {self.asset_category}")

		amount = self.gross_purchase_amount or self.total_asset_cost

		gl_entries = [
			frappe._dict(
				doctype="GL Entry",
				posting_date=self.purchase_date,
				account=fixed_asset_account,
				debit=amount,
				credit=0,
				debit_in_account_currency=amount,
				credit_in_account_currency=0,
				against=cwip_account,
				voucher_type=self.doctype,
				voucher_no=self.name,
				company=self.company,
				cost_center=self.cost_center,
				remarks=f"Asset capitalization - {self.asset_name}",
			),
			frappe._dict(
				doctype="GL Entry",
				posting_date=self.purchase_date,
				account=cwip_account,
				debit=0,
				credit=amount,
				debit_in_account_currency=0,
				credit_in_account_currency=amount,
				against=fixed_asset_account,
				voucher_type=self.doctype,
				voucher_no=self.name,
				company=self.company,
				cost_center=self.cost_center,
				remarks=f"Asset capitalization - {self.asset_name}",
			),
		]

		from erpnext.accounts.general_ledger import make_gl_entries
		make_gl_entries(gl_entries)

	def on_cancel(self):
		super().on_cancel()
		self.make_reverse_gl_entry()

	def make_reverse_gl_entry(self):
		from erpnext.accounts.general_ledger import make_reverse_gl_entries
		make_reverse_gl_entries(voucher_type=self.doctype, voucher_no=self.name)
				
	def make_asset_movement(self):
		reference_doctype = "Purchase Receipt" if self.purchase_receipt else "Purchase Invoice"
		reference_docname = self.purchase_receipt or self.purchase_invoice
		transaction_date = getdate(self.purchase_date)
		if reference_docname:
			posting_date, posting_time = frappe.db.get_value(
				reference_doctype, reference_docname, ["posting_date", "posting_time"]
			)
			transaction_date = get_datetime(f"{posting_date} {posting_time}")
		assets = [
			{
				"asset": self.name,
				"asset_name": self.asset_name,
				"target_location": self.location,	
				"target_unit": self.unit,
				"to_employee": self.custodian,
			}
		]
		asset_movement = frappe.get_doc(
			{
				"doctype": "Asset Movement",
				"assets": assets,
				"purpose": "Receipt",
				"company": self.company,
				"transaction_date": transaction_date,
				"reference_doctype": reference_doctype,
				"reference_name": reference_docname,
			}
		).insert()
		asset_movement.submit()

@frappe.whitelist()
def scrap_asset(asset_name, **kwargs):
	"""Scrap hanya boleh jalan lewat Asset Scrap Request yang sudah lolos 5 lapis
	approval. Tanpa penjaga ini, tombol/API bawaan ERPNext bisa melewati approval."""
	from erpnext.assets.doctype.asset.depreciation import scrap_asset as _scrap_asset

	if not frappe.flags.get("ignore_asset_scrap_request"):
		frappe.throw(
			_("Scrap Asset {0} harus lewat Asset Scrap Request yang sudah disetujui").format(asset_name),
			title=_("Butuh Approval")
		)

	return _scrap_asset(asset_name, **kwargs)


# Basis rasio pemecahan asset. split_asset bawaan ERPNext memakai
# split_qty/asset_quantity sebagai rasio pembagi semua nilai; dengan basis 10000
# rasio itu bisa diisi persentase sampai dua angka di belakang koma.
BASIS_SPLIT = 10000


def split_asset_by_persentase(asset_name, persentase, qty_split=1):
	"""Pecah Asset berdasarkan persentase nilai, bukan rasio qty.

	Dipakai scrap sebagian: asset ber-qty 1 pun bisa dipecah, misalnya bangunan
	yang rusak 30%. Fungsi bawaan ERPNext (create_new_asset_after_split dan
	update_existing_asset) tetap dipakai supaya jadwal penyusutan dan referensi
	Journal Entry ikut terbagi persis seperti split biasa; yang diganti cuma
	rasionya, lewat asset_quantity dokumen di memori. Qty yang sebenarnya
	dipasang ulang ke DB setelah pemecahan selesai.

	Mengembalikan nama Asset baru yang berisi bagian sebesar persentase itu."""
	from erpnext.assets.doctype.asset.asset import (
		create_new_asset_after_split,
		update_existing_asset,
	)

	persentase = flt(persentase)
	if persentase <= 0 or persentase >= 100:
		frappe.throw(
			_("Persentase pemecahan Asset harus di antara 0 dan 100, bukan {0}").format(persentase)
		)

	bagian = cint(round(BASIS_SPLIT * persentase / 100.0))
	if bagian < 1 or bagian >= BASIS_SPLIT:
		frappe.throw(_("Persentase {0} terlalu kecil untuk memecah Asset {1}").format(persentase, asset_name))

	asset = frappe.get_doc("Asset", asset_name)
	qty_total = cint(asset.asset_quantity) or 1

	qty_split = cint(qty_split) or 1
	if qty_total > 1:
		# asset sisa harus tetap punya qty, jadi pecahan paling banyak qty - 1
		qty_split = min(qty_split, qty_total - 1)
	qty_sisa = max(qty_total - qty_split, 1)

	# rasio pembagi kedua fungsi bawaan dibaca dari dokumen di memori ini
	asset.asset_quantity = BASIS_SPLIT

	asset_baru = create_new_asset_after_split(asset, bagian)
	update_existing_asset(asset, BASIS_SPLIT - bagian, asset_baru.name)

	# kedua fungsi di atas ikut menyimpan qty berbasis 10000 tadi, jadi qty yang
	# sebenarnya dipasang ulang di sini. ditulis langsung supaya tidak memicu
	# validasi Asset yang sudah disubmit
	frappe.db.set_value("Asset", asset_baru.name, "asset_quantity", qty_split, update_modified=False)
	frappe.db.set_value("Asset", asset_name, "asset_quantity", qty_sisa, update_modified=False)

	return asset_baru.name


@frappe.whitelist()
def make_sales_invoice(asset, item_code, company, serial_no=None):
	"""Override tombol 'Sell' di Asset. Isi Unit dari Asset dan set
	Jenis Penagihan = Disposal, supaya field Jenis Penagihan tidak
	kosong (yang defaultnya kebaca UI sebagai 'Pengiriman', opsi
	pertama di select) dan memicu validasi 'Sales Order wajib
	dipasang di Sales Invoice Pengiriman' saat disimpan.

	Penjualan hanya boleh setelah asset discrap lewat Asset Scrap Request."""
	from erpnext.assets.doctype.asset.asset import make_sales_invoice as _make_sales_invoice

	status = frappe.db.get_value("Asset", asset, "status")
	if status != "Scrapped":
		frappe.throw(
			_("Asset {0} harus discrap dulu sebelum bisa dijual. Status sekarang: {1}").format(asset, status),
			title=_("Belum Discrap")
		)

	si = _make_sales_invoice(asset, item_code, company, serial_no=serial_no)

	asset_doc = frappe.get_cached_doc("Asset", asset)
	si.jenis_penagihan = "Disposal"
	si.unit = asset_doc.unit

	# Piutangnya juga dipaksa lagi di before_validate Sales Invoice; di sini supaya
	# form yang terbuka sudah menampilkan akun yang benar sebelum disimpan
	receivable_account = frappe.db.get_value(
		"Account",
		{"account_number": AKUN_PIUTANG_LAIN, "company": company, "is_group": 0},
		"name"
	)
	if receivable_account:
		si.debit_to = receivable_account

	return si


@frappe.whitelist()
def make_asset_movement(assets, purpose=None):
	import json

	if isinstance(assets, str):
		assets = json.loads(assets)

	if len(assets) == 0:
		frappe.throw(_("Atleast one asset has to be selected."))

	asset_movement = frappe.new_doc("Asset Movement")
	asset_movement.quantity = len(assets)
	if purpose:
		asset_movement.purpose = purpose

	for asset in assets:
		asset = frappe.get_doc("Asset", asset.get("name"))
		asset_movement.company = asset.get("company")
		asset_movement.append(
			"assets",
			{
				"asset": asset.get("name"),
				"source_location": asset.get("location"),
				"from_employee": asset.get("custodian"),
				"source_unit": asset.get("unit"),
				"target_location": asset.get("location"),
			},
		)

	if asset_movement.get("assets"):
		return asset_movement.as_dict()

@frappe.whitelist()
def get_values_from_purchase_doc(purchase_doc_name, item_code, doctype):
	purchase_doc = frappe.get_doc(doctype, purchase_doc_name)
	matching_items = [item for item in purchase_doc.items if item.item_code == item_code]

	if not matching_items:
		frappe.throw(_(f"Selected {doctype} does not contain the Item Code {item_code}"))

	first_item = matching_items[0]

	return {
		"company": purchase_doc.company,
		"purchase_date": purchase_doc.get("bill_date") or purchase_doc.get("posting_date"),
		"gross_purchase_amount": flt(first_item.base_net_amount / first_item.qty),
		"asset_quantity": 1,
		"cost_center": first_item.cost_center or purchase_doc.get("cost_center"),
		"asset_location": first_item.get("asset_location"),
		"purchase_receipt_item": first_item.name if doctype == "Purchase Receipt" else None,
		"purchase_invoice_item": first_item.name if doctype == "Purchase Invoice" else None,
	}
	
@frappe.whitelist()
def validate_company(self,method):
	self.asset_owner_company = self.company

def validate_asset_for_vra_progress(doc, method):

	if not doc.asset_category:
		return

	create_vra_progress, tipe_master, jenis_alat = frappe.get_cached_value(
		"Asset Category",
		doc.asset_category,
		["create_vra_progress", "tipe_master", "jenis_alat"]
	)

	if not create_vra_progress:
		return

	missing_fields = []

	if not tipe_master:
		missing_fields.append("Tipe Master")

	if not jenis_alat:
		missing_fields.append("Jenis Alat")

	if missing_fields:
		frappe.throw(
			f"Asset Category <b>{doc.asset_category}</b> tidak bisa membuat VRA Progress "
			f"karena field <b>{', '.join(missing_fields)}</b> kosong."
		)

	make_vra_progress_from_asset(doc)


def make_vra_progress_from_asset(asset):

	tipe_master, jenis_alat = frappe.get_cached_value(
		"Asset Category",
		asset.asset_category,
		["tipe_master", "jenis_alat"]
	)

	divisi = None
	if asset.operator:
		divisi = frappe.get_cached_value(
			"Employee",
			asset.operator,
			"department"
		)

	uom = None
	if asset.item_code:
		uom = frappe.get_cached_value(
			"Item",
			asset.item_code,
			"stock_uom"
		)

	vra = frappe.get_doc({
		"doctype": "Alat Berat Dan Kendaraan",
		"tipe_master": tipe_master,
		"jns_alt": jenis_alat,
		"kode_item": asset.item_code,
		"nama_item": asset.item_name,
		"unit": asset.unit,
		"uom": uom,
		"asset": asset.name,
		"divis": divisi,
		"operator": asset.operator,
		"kmhm_akhir": 0,
		"api_status": "Aktif"
	})

	vra.insert(ignore_permissions=True)
