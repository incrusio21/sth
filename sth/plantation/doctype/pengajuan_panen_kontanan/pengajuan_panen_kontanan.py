# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import unscrub
from frappe.exceptions import DoesNotExistError
from frappe.utils import flt, get_link_to_form

from sth.controllers.plantation_controller import PlantationController

class PengajuanPanenKontanan(PlantationController):

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.skip_calculate_table = ["hasil_panen"]
		self.supervisi_list = ["mandor", "mandor1", "kerani"]

	def validate(self):
		self.get_data_bkm_panen()
		self.get_plantation_setting()
		self.set_missing_value()
		super().validate()

	def get_data_bkm_panen(self):
		self.set("hasil_panen", 
			frappe.get_all(
				"Detail BKM Hasil Kerja Panen", 
				filters={"parent": self.bkm_panen}, 
				fields=["employee", "qty", "sub_total as amount"]
			)  
		)

	def get_plantation_setting(self):
		from sth.plantation import get_plantation_settings

		for fieldname in ["supervisi_kontanan_component", "against_kontanan_component"]:
			self.set(fieldname, get_plantation_settings(fieldname))

	def before_calculate_grand_total(self):
		self.upah_supervisi_amount = flt(self.upah_mandor) + flt(self.upah_mandor1) + flt(self.upah_kerani)
	
	def before_submit(self):
		self.validate_account_and_salary_component()

	def validate_account_and_salary_component(self):
		if not (self.salary_account and self.credit_to):
			frappe.throw("Please set Account first")

	def on_submit(self):
		self.validate_duplicate_ppk()
		self.check_status_bkm_panen()
		self.create_or_update_epl_supervisi()
		self.make_gl_entry()

	def validate_duplicate_ppk(self):
		if dup_ppk := frappe.db.get_value("Pengajuan Panen Kontanan", 
			{
				"bkm_panen": self.bkm_panen,
				"name": ["!=", self.name],
				"docstatus": 1
			}, "name"
		):
			frappe.throw("{} is already use in <b>{}</b>".format("Buku Kerja Mandor Panen", get_link_to_form(self.doctype, dup_ppk)))

	def create_or_update_epl_supervisi(self):
		for emp in self.supervisi_list:
			try:
				doc = frappe.get_last_doc("Employee Payment Log", {
					"voucher_type": self.doctype,
					"voucher_no": self.name,
					"component_type": unscrub(emp)
				})
			except DoesNotExistError:
				is_new = True
				doc = frappe.new_doc("Employee Payment Log")

			amount = self.get(f"upah_{emp}") or 0
			# jika ada nilai atau kosong 
			if amount:
				doc.employee = self.get(emp)
				doc.company = self.company

				doc.posting_date = self.posting_date
				doc.payroll_date = self.posting_date

				doc.amount = amount

				doc.salary_component = self.get("supervisi_component")
				doc.against_salary_component = self.get("against_kontanan_component")

				doc.voucher_type = self.doctype
				doc.voucher_no = self.name
				doc.component_type = "Kontanan"
				# if log_updater.get("target_account"):
				# 	doc.account = self.get(log_updater["target_account"])

				doc.save()
			else:
				# removed jika nilai kosong dan bukan document baru
				if not is_new:
					doc.delete()
			
	def on_cancel(self):
		super().on_cancel()
		self.check_status_bkm_panen()
		self.delete_employee_payment_log()
		self.make_gl_entry()

	def check_status_bkm_panen(self):
		doc = frappe.get_doc("Buku Kerja Mandor Panen", self.bkm_panen)
		doc.update_kontanan_used()

	def delete_employee_payment_log(self):
		for epl in frappe.get_all(
			"Employee Payment Log", 
			filters={"voucher_type": self.doctype, "voucher_no": self.name}, 
			pluck="name"
		):
			frappe.delete_doc("Employee Payment Log", epl, flags=frappe._dict(transaction_employee=True))