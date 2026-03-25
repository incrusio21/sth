# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AssetDepreciationFiscal(Document):
	def validate(doc):
		self = frappe.get_doc("Asset", doc.asset)

		self._start_year = frappe.utils.getdate(doc.purchase_date).year

		years = int(doc.total_depreciation_fiscal)
		annual_amount = frappe.utils.flt(
			self.gross_purchase_amount / years, precision=2
		)

		doc.asset_depreciation_fiscal_table = []

		accumulated = 0.0
		for i in range(years):
			year = self._start_year + i
			accumulated = frappe.utils.flt(accumulated + annual_amount, precision=2)

			if i == years - 1:
				accumulated = frappe.utils.flt(self.gross_purchase_amount, precision=2)

			doc.append(
				"asset_depreciation_fiscal_table",
				{
					"year": year,
					"depreciation_amount": annual_amount,
					"accumulated_depreciation_amount": accumulated,
				},
			)
