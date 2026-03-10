# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AnalisaKualitasCPOPengiriman(Document):
	def before_submit(self):
		ikf = self.input_kualitas_ffa_
		ikm = self.input_kualitas_moisture_
		ikd = self.input_kualitas_dirt_

		# cari timbangan dengan no ticket ini
		list_timbangan = frappe.db.sql(""" SELECT name FROM `tabTimbangan` WHERE ticket_number = "{}" and docstatus < 2 """.format(self.ticket_number))
		for row in list_timbangan:
			print(row[0])
			doc = frappe.get_doc("Timbangan", row[0])
			doc.kualitas_ffa_ = ikf
			doc.kualitas_moisture_ = ikm
			doc.kualitas_dirt_ = ikd
			doc.db_update()
