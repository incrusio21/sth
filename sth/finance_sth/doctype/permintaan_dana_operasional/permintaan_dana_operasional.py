# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from sth.finance_sth.doctype.pdo_bahan_bakar_vtwo.pdo_bahan_bakar_vtwo import process_pdo_bahan_bakar
from sth.finance_sth.doctype.pdo_perjalanan_dinas_vtwo.pdo_perjalanan_dinas_vtwo import process_pdo_perjalanan_dinas
from sth.finance_sth.doctype.pdo_kas_vtwo.pdo_kas_vtwo import process_pdo_kas
from sth.finance_sth.doctype.pdo_dana_cadangan_vtwo.pdo_dana_cadangan_vtwo import process_pdo_dana_cadangan
from sth.finance_sth.doctype.pdo_non_pdo_vtwo.pdo_non_pdo_vtwo import process_pdo_non_pdo

PROCESSORS_INSERT = {
	"Bahan Bakar": process_pdo_bahan_bakar,
	"Perjalanan Dinas": process_pdo_perjalanan_dinas,
	"Kas": process_pdo_kas,
	"Dana Cadangan": process_pdo_dana_cadangan,
	"NON PDO": process_pdo_non_pdo,
}
pdo_categories = ["Bahan Bakar", "Perjalanan Dinas", "Kas", "Dana Cadangan", "NON PDO"]

class PermintaanDanaOperasional(Document):
	def on_update(self):
		self.process_data_to_insert_vtwo()

	def on_submit(self):
		self.submit_pdo_vtwo()

	def before_cancel(self):
		self.cancel_pdo_vtwo()

	def process_data_to_insert_vtwo(self):
		for pdo in pdo_categories:
			fieldname = pdo.lower().replace(" ", "_")

			if not self.get(f"pdo_{fieldname}") and not self.get(f"{fieldname}_transaction_number"):
				continue
				
			data = {
				"grand_total": self.get(f"grand_total_{fieldname}"),
				"outstanding_amount": self.get(f"outstanding_amount_{fieldname}"),
				"debit_to": self.get(f"{fieldname}_debit_to"),
				"credit_to": self.get(f"{fieldname}_credit_to"),
				"reference_doc": "Permintaan Dana Operasional",
				"reference_name": self.name,
			}
			
			childs = self.get(f"pdo_{fieldname}")
			
			handlers = PROCESSORS_INSERT.get(pdo)
			if handlers:
				handlers(data, childs)
	
	def submit_pdo_vtwo(self):
		for pdo in pdo_categories:
			fieldname = pdo.lower().replace(" ", "_")

			if self.get(f"pdo_{fieldname}") and self.get(f"{fieldname}_transaction_number"):
				doctype_vtwo = f"PDO {pdo} Vtwo"
				docname_vtwo = self.get(f"{fieldname}_transaction_number")
				doc = frappe.get_doc(doctype_vtwo, docname_vtwo)
				doc.submit()
    
	def cancel_pdo_vtwo(self):
		for pdo in pdo_categories:
			fieldname = pdo.lower().replace(" ", "_")

			if self.get(f"pdo_{fieldname}") and self.get(f"{fieldname}_transaction_number"):
				doctype_vtwo = f"PDO {pdo} Vtwo"
				docname_vtwo = self.get(f"{fieldname}_transaction_number")
				doc = frappe.get_doc(doctype_vtwo, docname_vtwo)
				doc.cancel()