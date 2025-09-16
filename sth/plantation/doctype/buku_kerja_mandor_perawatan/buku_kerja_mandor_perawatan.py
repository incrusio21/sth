# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.query_builder.functions import Sum

from frappe.utils import flt
from sth.controllers.prev_doc_validate import validate_previous_document
from sth.controllers.plantation_controller import PlantationController

from hrms.hr.doctype.attendance.attendance import DuplicateAttendanceError

force_item_fields = (
	"rencana_kerja_harian",
	"voucher_type",
	"voucher_no"
)

class BukuKerjaMandorPerawatan(PlantationController, validate_previous_document):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

	def validate(self):
		self.get_rencana_kerja_harian()
		self.validate_hasil_kerja_harian()
		self.check_material()

		super().validate()
	
	def validate_hasil_kerja_harian(self):
		if self.uom == "HA" and self.hasil_kerja_qty > self.luas_blok:
			frappe.throw("Hasil Kerja exceeds Luas Blok")

		for hk in self.hasil_kerja:
			hk.hari_kerja = flt(hk.qty / self.volume_basis)
			hk.rate = hk.get("rate") or self.rp_per_basis

			if self.per_premi and hk.hari_kerja > flt(self.volume_basis * ((1 + self.per_premi) / 100)):
				hk.premi = self.rupiah_premi

	def get_rencana_kerja_harian(self):
		ret = get_rencana_kerja_harian(self.kode_kegiatan, self.divisi, self.blok, self.posting_date)
		for fieldname, value in ret.items():
			if self.meta.get_field(fieldname) and value is not None:
				if (
					self.get(fieldname) is None
					or fieldname in force_item_fields
				):
					self.set(fieldname, value)

	def on_submit(self):
		self.make_payment_log()
		self.make_attendance()
		self.check_emp_hari_kerja()
		
		if not self.material:
			self.update_rkb_realization()
		else:
			self.create_ste_issue()
			
	def make_payment_log(self):
		for emp in self.hasil_kerja:
			doc = frappe.new_doc("Employee Payment Log")

			doc.hari_kerja = emp.hari_kerja
			doc.amount = emp.amount

			doc.employee = emp.employee
			doc.company = self.company
			doc.attendance_date = self.posting_date

			doc.voucher_type = self.doctype
			doc.voucher_no = self.name

			doc.save()
	
	def make_attendance(self):
		for emp in self.hasil_kerja:
			attendance_detail = {
				"employee": emp.employee, "company": self.company, "attendance_date": self.posting_date
			}

			add_att = "add_attendance"
			try:
				frappe.db.savepoint(add_att)
				attendance = frappe.get_doc({
					"doctype": "Attendance",
					"status": emp.status,
					**attendance_detail
				})
				attendance.flags.ignore_permissions = 1
				attendance.submit()
			except DuplicateAttendanceError:
				if frappe.message_log:
					frappe.message_log.pop()
					
				frappe.db.rollback(save_point=add_att)  # preserve transaction in postgres

	def check_emp_hari_kerja(self):
		employee_list = [emp.employee for emp in self.hasil_kerja]

		payment_log = frappe.qb.DocType("Employee Payment Log")
		employee_hk = (
			frappe.qb.from_(payment_log)
			.select(
				payment_log.employee, Sum(payment_log.hari_kerja).as_("hari_kerja")
			)
			.where(
				(payment_log.employee.isin(employee_list)) &
				(payment_log.company == self.company) &
				(payment_log.posting_date == self.posting_date)
			)
			.groupby(payment_log.employee)
		).run(as_dict=1)

		for emp in employee_hk:
			if emp.hari_kerja > 1:
				frappe.throw("Employee {} exceeds Hari Kerja".format(emp.employee))
	
	def create_ste_issue(self):
		ste = frappe.new_doc("Stock Entry")
		ste.stock_entry_type = "Material Used"
		ste.set_purpose_for_stock_entry()

		for d in self.material:
			ste.append("items", {
				"s_warehouse": d.warehouse,
				"item_code": d.item,
				"qty": d.qty,
			})
		
		ste.submit()

		self.stock_entry = ste.name
		for index, item in enumerate(ste.items):
			self.material[index].update({
				"stock_entry_detail": item.name,
				"rate": item.basic_rate,
			})

		self.set_material_rate(get_valuation_rate=False)

	def set_material_rate(self, get_valuation_rate=True):
		if get_valuation_rate:
			for d in self.material:
				d.rate = frappe.get_value("Stock Entry Detail", d.stock_entry_detail, "basic_rate")
				
		self.calculate_item_table_values()
		self.calculate_grand_total()

		self.db_update_all()

		self.update_rkb_realization()

	def update_rkb_realization(self):
		frappe.get_doc(self.voucher_type, self.voucher_no).calculate_used_and_realized()

	def on_cancel(self):
		self.delete_payment_log()
		self.delete_ste()

		self.update_rkb_realization()

	def delete_payment_log(self):
		filters={"voucher_type": self.doctype, "voucher_no": self.name}
		for emp_log in frappe.get_all("Employee Payment Log", 
			filters=filters, pluck="name"
		):
			frappe.delete_doc("Employee Payment Log", emp_log)

	def delete_ste(self):
		if not self.stock_entry:
			return
			
		ste = frappe.get_doc("Stock Entry", self.stock_entry)
		if ste.docstatus == 1:
			ste.cancel()

		self.db_set("stock_entry", "")

		ste.delete()

@frappe.whitelist()
def get_rencana_kerja_harian(kode_kegiatan, divisi, blok, posting_date):
	rkh = frappe.get_value("Rencana Kerja Harian", {
		"kode_kegiatan": kode_kegiatan, "divisi": divisi, "blok": blok, "posting_date": posting_date,
		"docstatus": 1
	}, ["name as rencana_kerja_harian", "voucher_type", "voucher_no"], as_dict=1)

	if not rkh:
		frappe.throw(""" Rencana Kerja Harian not Found for Filters <br> 
			Kegiatan : {} <br> 
			Divisi : {} <br> 
			Blok : {} <br>
			Date : {} """.format(kode_kegiatan, divisi, blok, posting_date))

	# no rencana kerja harian
	ress = { 
		**rkh,
		"material": frappe.db.get_all("Detail RKH Material", 
			filters={"parent": rkh}, fields=["item", "uom"]
		) 
	}

	return ress