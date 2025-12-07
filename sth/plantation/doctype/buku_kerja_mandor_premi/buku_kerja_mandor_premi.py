# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.exceptions import DoesNotExistError
from frappe.utils import flt
from frappe.query_builder.functions import Sum, Count

from frappe.model.document import Document

class BukuKerjaMandorPremi(Document):
	def validate(self):
		self.get_amount_and_divided_by()
		self.calculate_grand_total()

	def get_amount_and_divided_by(self):
		Traksi = frappe.qb.DocType("Buku Kerja Mandor Traksi")

		# Group by kategori tertentu
		self.amount, self.divided_by = (
			frappe.qb.from_(Traksi)
			.select(
				Sum(Traksi.amount),
				Count(Traksi.name)
			)
			.where(
				(Traksi.mandor == self.employee) & 
				(Traksi.company == self.company) & 
				(Traksi.posting_date == self.posting_date)
			)
		).run()[0] or [0, 0]

	def calculate_grand_total(self):
		self.grand_total = flt(1.4 * self.amount / (self.divided_by or 1), self.precision("grand_total"))
		
	def create_or_update_payment_log(self):
		try:
			doc = frappe.get_last_doc("Employee Payment Log", {
				"voucher_type": self.doctype,
				"voucher_no": self.name
			})
		except DoesNotExistError:
			doc = frappe.new_doc("Employee Payment Log")
		
		# jika ada nilai atau kosong tapi tidak di hapus 
		doc.employee = self.employee
		doc.company = self.company
		doc.posting_date = self.posting_date
		doc.payroll_date = self.posting_date

		doc.amount = self.grand_total

		# details
		doc.voucher_type = self.doctype
		doc.voucher_no = self.name

		doc.salary_component = self.salary_component
		doc.save()
		
	def on_trash(self):
		for epl in frappe.get_all(
			"Employee Payment Log", 
			filters={"voucher_type": self.doctype, "voucher_no": self.name}, 
			pluck="name"
		):
			frappe.delete_doc("Employee Payment Log", epl, flags=frappe._dict(transaction_employee=True))

def on_doctype_update():
	frappe.db.add_unique("Buku Kerja Mandor Premi", ["employee", "posting_date"], constraint_name="unique_item_warehouse")