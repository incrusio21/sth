# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from erpnext.stock.doctype.delivery_note.delivery_note import DeliveryNote

class DeliveryOrder(DeliveryNote):
	def on_submit(self):
		pass

	def on_cancel(self):
		pass
