# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.query_builder.functions import Sum

from frappe.utils import flt, get_link_to_form
from sth.controllers.plantation_controller import PlantationController
from hrms.hr.doctype.attendance.attendance import DuplicateAttendanceError

force_item_fields = (
	"rencana_kerja_harian"
)

class BukuKerjaMandorPerawatan(PlantationController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.skip_calculate_table = ["material"]

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

	def check_material(self):
		material_list = [m.item for m in self.material]
		if not material_list:
			return
		
		rkb_m = frappe.qb.DocType("Detail RKH Material")
		material_used = frappe._dict(
			(
				frappe.qb.from_(rkb_m)
				.select(
					rkb_m.item, rkb_m.name
				)
				.where(
					(rkb_m.item.isin(material_list)) &
					(rkb_m.parent == self.rencana_kerja_harian)
				)
				.groupby(rkb_m.item)
			).run()
		)

		for d in self.material:
			rkb_material = material_used.get(d.item) or ""
			if not rkb_material:
				frappe.throw("Item {} is not listed in the {}.".format(d.item, get_link_to_form("Rencana Kerja Harian",self.rencana_kerja_harian)))

			d.prevdoc_detail = rkb_material

	def on_submit(self):
		self.make_payment_log()
		self.make_attendance()
		self.check_emp_hari_kerja()
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
		if not self.material:
			return
		
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

		self.db_set("stock_entry", ste.name)

	def on_cancel(self):
		self.delete_payment_log()
		self.delete_ste()

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
	}, "name")

	if not rkh:
		frappe.throw(""" Rencana Kerja Harian not Found for Filters <br> 
			Kegiatan : {} <br> 
			Divisi : {} <br> 
			Blok : {} <br>
			Date : {} """.format(kode_kegiatan, divisi, blok, posting_date))

	# no rencana kerja harian
	ress = { 
		"rencana_kerja_harian": rkh,
		"material": frappe.db.get_all("Detail RKH Material", 
			filters={"parent": rkh},fields=["item", "uom", "name as prevdoc_detail"]
		) 
	}

	return ress