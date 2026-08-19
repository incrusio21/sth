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


@frappe.whitelist()
def restore_asset(asset_name):
	"""Restore Asset sekaligus membatalkan pengajuan scrap yang menjalankannya.

	Scrap penuh dijalankan Asset Scrap Request, dan pembatalannya sengaja
	diarahkan ke tombol Restore Asset ini — lihat on_cancel di Asset Scrap
	Request. Tanpa pembatalan itu pengajuannya tetap Approved sementara asetnya
	sudah hidup lagi: status_scrap di Asset masih terisi dan qty_scrapped-nya
	tidak kembali nol, sehingga asetnya masih terlihat boleh dijual lewat Sales
	Invoice Disposal.

	Jurnal scrapnya dicari dulu sebelum restore berjalan, karena dua hal:
	restore bawaan melepas journal_entry_for_scrap dari Asset — padahal itu
	penanda paling pasti pengajuan mana yang menjalankan scrap ini — dan
	tautan jurnal di pengajuannya harus dilepas lebih dulu. Restore membatalkan
	jurnal itu, sedangkan frappe menolak membatalkan dokumen yang masih ditunjuk
	dokumen tersubmit lain (LinkExistsError).
	"""
	from erpnext.assets.doctype.asset.depreciation import restore_asset as _restore_asset

	journal_entry = frappe.db.get_value("Asset", asset_name, "journal_entry_for_scrap")
	pengajuan = cari_pengajuan_scrap_penuh(asset_name, journal_entry)

	if pengajuan:
		frappe.db.set_value(
			"Asset Scrap Request", pengajuan, "journal_entry_for_scrap", None,
			update_modified=False
		)

	hasil = _restore_asset(asset_name)

	if pengajuan:
		batalkan_pengajuan_scrap(pengajuan)

	return hasil


def cari_pengajuan_scrap_penuh(asset_name, journal_entry=None):
	"""Asset Scrap Request yang menjalankan scrap penuh sebuah asset.

	Pengajuan scrap sebagian sengaja tidak dicari: jurnalnya berdiri sendiri dan
	tidak disentuh Restore Asset, jadi hapus bukunya tetap berlaku.
	"""
	from sth.accounting_sth.doctype.asset_scrap_request.asset_scrap_request import STATE_APPROVED

	if journal_entry:
		nama = frappe.db.get_value(
			"Asset Scrap Request",
			{"asset": asset_name, "docstatus": 1, "journal_entry_for_scrap": journal_entry},
			"name",
		)
		if nama:
			return nama

	# pengajuan lama tidak selalu menyimpan jurnalnya. Rejected juga berdocstatus
	# 1 tapi tidak pernah menjalankan scrap, jadi disaring lewat workflow_state.
	kandidat = frappe.get_all(
		"Asset Scrap Request",
		filters={"asset": asset_name, "docstatus": 1, "persentase_scrap": (">=", 100)},
		fields=["name", "workflow_state"],
		order_by="creation desc",
	)

	for d in kandidat:
		if not d.workflow_state or d.workflow_state == STATE_APPROVED:
			return d.name

	return None


def batalkan_pengajuan_scrap(nama):
	"""Batalkan pengajuan scrap sebagai bagian dari Restore Asset.

	Flag-nya dibaca on_cancel di Asset Scrap Request: pembatalan scrap penuh
	hanya boleh lewat jalur ini, tidak langsung dari pengajuannya.
	"""
	doc = frappe.get_doc("Asset Scrap Request", nama)

	frappe.flags.restore_asset_berjalan = True
	try:
		doc.cancel()
	finally:
		frappe.flags.restore_asset_berjalan = False


def sisa_qty_scrap(asset, kecuali_sales_invoice=None):
	"""Qty asset yang sudah discrap dan belum terjual.

	Yang dibaca cuma qty_scrapped. Angka itu dicatat eksplisit waktu Asset Scrap
	Request disetujui, baik scrap sebagian maupun seluruhnya.

	Sebelumnya scrap penuh disimpulkan dari status == "Scrapped". Status itu
	berubah jadi "Sold" begitu asetnya dijual dan tidak dikembalikan waktu
	invoicenya dibatalkan, jadi asetnya tersangkut: qty_scrapped 0 dan status
	bukan "Scrapped" lagi, sehingga tidak pernah bisa dijual ulang.

	Sales Invoice Disposal yang masih draft ikut dihitung supaya dua invoice
	tidak sama-sama menghabiskan jatah."""
	doc = frappe.db.get_value("Asset", asset, ["qty_scrapped"], as_dict=True)

	if not doc:
		return 0

	discrap = cint(doc.qty_scrapped)

	if not discrap:
		return 0

	terjual = frappe.db.sql("""
		SELECT COALESCE(SUM(sii.qty), 0)
		FROM `tabSales Invoice Item` sii
		JOIN `tabSales Invoice` si ON si.name = sii.parent
		WHERE sii.asset = %(asset)s
		  AND si.docstatus != 2
		  AND si.jenis_penagihan = 'Disposal'
		  AND si.name != %(kecuali)s
	""", {"asset": asset, "kecuali": kecuali_sales_invoice or ""})[0][0]

	return max(discrap - flt(terjual), 0)


@frappe.whitelist()
def make_sales_invoice(asset, item_code, company, serial_no=None):
	"""Override tombol 'Sell' di Asset. Isi Unit dari Asset dan set
	Jenis Penagihan = Disposal, supaya field Jenis Penagihan tidak
	kosong (yang defaultnya kebaca UI sebagai 'Pengiriman', opsi
	pertama di select) dan memicu validasi 'Sales Order wajib
	dipasang di Sales Invoice Pengiriman' saat disimpan.

	Penjualan hanya boleh setelah asset discrap lewat Asset Scrap Request, dan
	paling banyak sebanyak qty yang sudah discrap."""
	from erpnext.assets.doctype.asset.asset import make_sales_invoice as _make_sales_invoice

	sisa = sisa_qty_scrap(asset)
	if not sisa:
		status = frappe.db.get_value("Asset", asset, "status")
		frappe.throw(
			_("Asset {0} harus discrap dulu sebelum bisa dijual, dan bagian yang discrap "
			  "belum tentu masih ada sisanya. Status sekarang: {1}").format(asset, status),
			title=_("Belum Discrap")
		)

	si = _make_sales_invoice(asset, item_code, company, serial_no=serial_no)

	asset_doc = frappe.get_cached_doc("Asset", asset)
	si.jenis_penagihan = "Disposal"
	si.unit = asset_doc.unit

	# qty bawaannya selalu 1; yang boleh dijual sebanyak yang sudah discrap
	for item in si.items:
		item.qty = sisa

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
