# Copyright (c) 2026 DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils import flt

from sth.utils.data import tax_rate

def validate_custom_tax(self, method=None):
		self.taxes = []

		tax_list = []
		if self.ppn:
			tax = tax_rate(self.company, self.ppn, "Masukan")
			self.ppn_account = tax["account"]
			self.ppn_rate = tax["rate"]
			self.ppn_amount = flt(self.net_total * self.ppn_rate)

			tax_list.append({
				"account": self.ppn_account,
				"amount": self.ppn_amount
			})
		
		for pph in self.pph_details:
			tax = tax_rate(self.company, pph.type)
			pph.account = tax["account"]
			pph.percentage = tax["rate"]
			pph.amount = flt(self.net_total * pph.percentage)

			tax_list.append({
				"account": pph.account,
				"add_deduct": "Deduct",
				"amount": pph.amount
			})

		for t in tax_list:
			self.append("taxes", {
				"category": "Total",
				"description": frappe.get_cached_value("Account", t.get("account"), "account_name"),
				"charge_type": "Actual",
				"add_deduct_tax": t.get("add_deduct") or "Add",
				"account_head": t.get("account"),
				"tax_amount": t.get("amount"),
				"tax_amount": t.get("amount"),
			})