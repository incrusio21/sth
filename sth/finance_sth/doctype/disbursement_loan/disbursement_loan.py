# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class DisbursementLoan(Document):
	pass


def make_disbursement_loan(data):
    doc = frappe.get_doc(data)
    doc.insert()