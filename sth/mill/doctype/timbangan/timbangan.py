# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime
from sth.mill.doctype.tbs_ledger_entry.tbs_ledger_entry import create_tbs_ledger,reverse_tbs_ledger

class Timbangan(Document):
	def on_submit(self):
		if self.type == "Receive":
			for row in self.items:
				create_tbs_ledger(frappe._dict({
					"item_code": row.item_code,
					"posting_date": self.posting_date,
					"posting_time" : self.posting_time,
					"posting_datetime": get_datetime(f"{self.posting_date} {self.posting_time}"),
					"type": self.receive_type,
					"voucher_type": self.doctype,
					"voucher_no": self.name,
					"balance_qty": row.netto - (self.potongan_sortasi/100),
				}))

	def on_cancel(self):
		self.ignore_linked_doctypes = (
			"TBS Ledger Entry"
		)
		
		if self.type == "Receive":
			reverse_tbs_ledger(self.name)