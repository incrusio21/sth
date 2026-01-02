# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.utils import flt, get_last_day
from frappe.exceptions import DoesNotExistError
from frappe.query_builder.functions import Sum, Count

from frappe.model.document import Document

from sth.plantation import get_plantation_settings

voucher_maping = {
	"Traksi": "tbs_amount",
	"Panen": "qty",
}

class BukuKerjaMandorPremi(Document):
	def before_insert(self):
		self.set_missing_values()

	def set_missing_values(self):
		mandor_premi = get_plantation_settings("mandor_premi")
		have_premi = False
		voucher_type = f"Buku Kerja Mandor {self.buku_kerja_mandor}"
		for p in mandor_premi:
			if p.voucher_type != voucher_type or p.employee_field != self.mandor_type:
				continue
			
			have_premi = True
			self.multiplier = p.multiplier
			self.method = p.method
			self.salary_component = p.salary_component
		
		if not have_premi:
			frappe.throw(f"Please set Mandor Premi Setting for {self.buku_kerja_mandor} in Plantation Settings")
	
	def validate(self):
		self.set_amount_employee()
		self.calculate_grand_total()

	def set_amount_employee(self):
		# get total dari voucher type tertentu
		bkm = frappe.qb.DocType(f"Buku Kerja Mandor {self.buku_kerja_mandor}")
		detail_hk = frappe.qb.DocType(f"Detail BKM Hasil Kerja {self.buku_kerja_mandor}")
		
		fields = voucher_maping.get(self.buku_kerja_mandor)

		# Group by kategori tertentu
		self.employee_list = json.dumps(
			frappe._dict(
				(
					frappe.qb.from_(bkm)
					.inner_join(detail_hk)
					.on(bkm.name == detail_hk.parent)
					.select(
						detail_hk.employee,
						Sum(detail_hk[fields]),
					)
					.where(
						(bkm.docstatus == 1) & 
						(bkm[self.mandor_type] == self.employee) & 
						(bkm.company == self.company) & 
						(bkm.posting_date.between(self.posting_date, get_last_day(self.posting_date)))
					)
					.groupby(detail_hk.employee)
				).run()
			)
		)

	def calculate_grand_total(self):
		employee = json.loads(self.employee_list)
		
		amount = total_emp = 0
		for emp, amm in employee.items():
			total_emp += 1
			amount += amm

		self.amount = amount
		if self.method == "Average":
			amount = amount / total_emp
			self.average = amount
			
		self.grand_total = flt(amount * self.multiplier, self.precision("grand_total"))

	def on_update(self):
		if not self.grand_total:
			self.delete()
		else:
			self.create_or_update_payment_log()

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
		self.remove_document()

		for epl in frappe.get_all(
			"Employee Payment Log", 
			filters={"voucher_type": self.doctype, "voucher_no": self.name}, 
			pluck="name"
		):
			frappe.delete_doc("Employee Payment Log", epl, flags=frappe._dict(transaction_employee=True))

	def remove_document(self):
		# skip jika berasal dari transaksi
		if self.flags.transaction_employee:
			return
		
		msg = _("Individual Buku Kerja Mandor Premi cannot be deleted.")
		msg += "<br>" + _("Please cancel related transaction.")
		frappe.throw(msg)

def on_doctype_update():
	frappe.db.add_unique("Buku Kerja Mandor Premi", ["employee", "mandor_type", "company", "buku_kerja_mandor", "posting_date"], constraint_name="uniqe_employe_voucher")