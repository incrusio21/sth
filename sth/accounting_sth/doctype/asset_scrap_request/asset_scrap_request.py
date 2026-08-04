# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

STATE_APPROVED = "Approved"

# status asset yang tidak bisa lagi diajukan scrap
STATUS_TIDAK_BISA_SCRAP = ("Draft", "Cancelled", "Sold", "Scrapped", "Capitalized", "Decapitalized")


class AssetScrapRequest(Document):

	def validate(self):
		self.validate_asset()
		self.validate_duplikat()
		self.set_nilai_buku()

	def validate_asset(self):
		asset = frappe.db.get_value(
			"Asset", self.asset, ["docstatus", "status", "company"], as_dict=True
		)

		if not asset:
			frappe.throw(_("Asset {0} tidak ditemukan").format(self.asset))

		if asset.docstatus != 1:
			frappe.throw(_("Asset {0} belum disubmit").format(self.asset))

		if asset.status in STATUS_TIDAK_BISA_SCRAP:
			frappe.throw(
				_("Asset {0} tidak bisa discrap karena statusnya {1}").format(self.asset, asset.status)
			)

	def validate_duplikat(self):
		pengajuan_lain = frappe.db.exists(
			"Asset Scrap Request",
			{
				"asset": self.asset,
				"docstatus": ["<", 2],
				"name": ["!=", self.name]
			}
		)

		if pengajuan_lain:
			frappe.throw(
				_("Asset {0} sudah punya pengajuan scrap yang berjalan di {1}").format(
					self.asset, pengajuan_lain
				)
			)

	def set_nilai_buku(self):
		asset = frappe.get_doc("Asset", self.asset)

		if asset.calculate_depreciation and asset.get("finance_books"):
			nilai_buku = flt(asset.finance_books[0].value_after_depreciation)
		else:
			nilai_buku = flt(asset.value_after_depreciation) or (
				flt(asset.gross_purchase_amount) - flt(asset.opening_accumulated_depreciation)
			)

		self.nilai_buku = flt(nilai_buku, self.precision("nilai_buku"))

	def on_submit(self):
		# workflow punya dua state ber-docstatus 1: Approved dan Rejected.
		# yang boleh menjalankan scrap cuma Approved.
		if self.get("workflow_state") and self.workflow_state != STATE_APPROVED:
			return

		self.scrap_asset()

	def scrap_asset(self):
		# import langsung supaya tidak kena penjaga di sth.overrides.asset.scrap_asset
		from erpnext.assets.doctype.asset.depreciation import scrap_asset

		self.validate_asset()

		frappe.flags.ignore_asset_scrap_request = True
		try:
			scrap_asset(self.asset)
		finally:
			frappe.flags.ignore_asset_scrap_request = False

		journal_entry = frappe.db.get_value("Asset", self.asset, "journal_entry_for_scrap")
		if journal_entry:
			self.db_set("journal_entry_for_scrap", journal_entry)

	def on_cancel(self):
		if self.journal_entry_for_scrap:
			frappe.throw(
				_("Asset {0} sudah discrap. Batalkan lewat tombol Restore Asset di Asset tersebut.").format(
					self.asset
				)
			)
