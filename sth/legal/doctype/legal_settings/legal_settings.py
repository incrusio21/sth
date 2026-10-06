# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class LegalSettings(Document):
	def validate(self):
		self.validate_default_item_code()

	def validate_default_item_code(self):
		"""Item global baris kegiatan Proposal/BAPP tidak boleh item stok.

		Item ini cuma pengisi item code untuk pekerjaan, bukan barang yang
		diterima, jadi tidak boleh sampai menggerakkan stok di dokumen turunannya.
		"""
		if self.default_item_code and frappe.db.get_value("Item", self.default_item_code, "is_stock_item"):
			frappe.throw(_("Default Item Code {0} harus item non-stok.").format(frappe.bold(self.default_item_code)))
