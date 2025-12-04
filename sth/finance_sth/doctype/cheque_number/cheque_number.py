# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ChequeNumber(Document):
	pass

def update_cheque_number_pe(cheque_number, data):
	doc = frappe.get_doc("Cheque Number", cheque_number)
	doc.status = data.status
	doc.reference_doc = data.reference_doc
	doc.reference_name = data.reference_name
	doc.cheque_amount = data.cheque_amount
	doc.note = data.note
	doc.issue_date = data.issue_date
	doc.upload_cheque_book = data.upload_cheque_book
	doc.db_update_all()

	return doc