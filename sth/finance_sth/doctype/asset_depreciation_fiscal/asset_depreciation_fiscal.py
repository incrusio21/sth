# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AssetDepreciationFiscal(Document):
	def validate(doc):
		self = frappe.get_doc("Asset", doc.asset)
		start_date = frappe.utils.getdate(doc.purchase_date)
		self._start_year = start_date.year
		self._start_month = start_date.month

		months = int(doc.total_depreciation_fiscal)
		monthly_amount = frappe.utils.flt(
			self.gross_purchase_amount / months, precision=2
		)

		doc.asset_depreciation_fiscal_table = []
		accumulated = 0.0

		for i in range(months):
			month_offset = self._start_month - 1 + i
			year = self._start_year + month_offset // 12
			month = month_offset % 12 + 1

			accumulated = frappe.utils.flt(accumulated + monthly_amount, precision=2)
			if i == months - 1:
				accumulated = frappe.utils.flt(self.gross_purchase_amount, precision=2)

			doc.append(
				"asset_depreciation_fiscal_table",
				{
					"year": year,
					"month": month,
					"depreciation_amount": monthly_amount,
					"accumulated_depreciation_amount": accumulated,
				},
			)