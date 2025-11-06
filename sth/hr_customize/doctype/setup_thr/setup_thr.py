# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import calendar, datetime

class SetupTHR(Document):
	@frappe.whitelist()
	def get_setup_rate_thr(self):
		uang_daging = frappe.db.get_value("Company", self.company, "custom_uang_daging")
		natura_rate = frappe.get_all(
			"Natura Price",
			filters={"company": self.company},
			fields=["harga_beras", "valid_from"],
			order_by="valid_from desc",
			limit=1
		)
		days = calendar.monthrange(datetime.date.today().year, datetime.date.today().month)[1]

		return {
			"uang_daging": uang_daging,
			"natura_rate": natura_rate[0]["harga_beras"] if natura_rate else 0,
			"payment_days": days
		}

