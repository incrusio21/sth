# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ChequeBook(Document):
    
	def on_update(self):
		self.make_cheque_number()

	def make_cheque_number(self):
		start_no = int(self.cheque_start_no)
		end_no = int(self.cheque_end_no) + 1
		cheque_total = end_no - start_no
		for i in range(start_no, end_no):
			doc = frappe.get_doc({
				'doctype': 'Cheque Number',
				'number': i,
				'cheque_book': self.name
			})
			doc.insert()

		self.cheques_total = cheque_total
		self.remaining_cheques = cheque_total