# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import get_link_to_form

from sth.controllers.plantation_controller import PlantationController


class PengajuanPanenKontanan(PlantationController):

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.supervisi_list = ["mandor", "mandor1", "kerani"]

	def validate(self):
		self.get_data_bkm_panen()
		super().validate()

	def get_data_bkm_panen(self):
		pass

	def on_submit(self):
		self.validate_duplicate_ppk()
		self.check_status_bkm_panen()
		self.create_or_update_epl_supervisi()

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
			is_new = False
			target_link = f"{emp}_epl"

			if target_key := self.get(target_link):
				doc = frappe.get_doc("Employee Payment Log", target_key)
			else:
				is_new = True
				doc = frappe.new_doc("Employee Payment Log")

			amount = self.get(f"upah_{emp}") or 0

			# jika ada nilai atau kosong 
			if amount:
				doc.employee = self.get("employee")
				doc.company = self.company
				doc.posting_date = self.posting_date
				doc.payroll_date = self.payroll_date

				doc.status = "Approved"
				doc.amount = amount

				doc.salary_component = self.get("salary_component")
				doc.against_salary_component = self.get("against_salary_component")

				# if log_updater.get("target_account"):
				# 	doc.account = self.get(log_updater["target_account"])

				doc.save()

				detail_name = doc.name
			else:
				# removed jika nilai kosong dan bukan document baru
				if not is_new:
					doc.delete()
			
			self.set(target_link, detail_name)
		
	def on_cancel(self):
		self.check_status_bkm_panen()
		self.delete_payment_log()

	def check_status_bkm_panen(self):
		doc = frappe.get_doc("Buku Kerja Mandor Panen", self.bkm_panen)
		doc.update_kontanan_used()

	def delete_payment_log(self):
		for emp in self.supervisi_list:
			target_link = f"{emp}_epl"
			value = self.get(target_link)
			if not value:
				continue
			
			self.db_set(target_link, "")
			frappe.delete_doc("Employee Payment Log", value)