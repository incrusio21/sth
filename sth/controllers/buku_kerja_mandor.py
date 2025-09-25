# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.query_builder.functions import Sum

from hrms.hr.doctype.attendance.attendance import DuplicateAttendanceError

from sth.controllers.plantation_controller import PlantationController

force_item_fields = (
	"rencana_kerja_harian",
	"voucher_type",
	"voucher_no"
)

class BukuKerjaMandorController(PlantationController):
    
    def validate(self):
        self.get_rencana_kerja_harian()
        self.validate_hasil_kerja_harian()
        self.validate_previous_document()
        self.get_employee_payment_account()
        super().validate()

    def get_rencana_kerja_harian(self):
        from sth.controllers.queries import get_rencana_kerja_harian

        ret = get_rencana_kerja_harian(self.kode_kegiatan, self.divisi, self.blok, self.posting_date)
        for fieldname, value in ret.items():
            if self.meta.get_field(fieldname) and value is not None:
                if (
                    self.get(fieldname) is None
                    or fieldname in force_item_fields
                ):
                    self.set(fieldname, value)

    def validate_hasil_kerja_harian(self):
        if self.get("is_bibitan"):
            return
        
        if self.uom == "HA" and self.hasil_kerja_qty > self.luas_blok:
            frappe.throw("Hasil Kerja exceeds Luas Blok")

    def validate_previous_document(self):
        from sth.controllers.prev_doc_validate import validate_previous_document

        validate_previous_document(self)

    def get_employee_payment_account(self):
        self.employee_payment_account = frappe.get_cached_value("Company", self.company, "employee_payment_account")

    def on_submit(self, update_realization=True):
        self.make_payment_log()
        self.create_journal_entry()
        self.make_attendance()
        self.check_emp_hari_kerja()

        if update_realization:
            self.update_rkb_realization()

    def make_payment_log(self):
        for emp in self.hasil_kerja:
            doc = frappe.new_doc("Employee Payment Log")

            doc.hari_kerja = emp.qty
            doc.amount = emp.amount

            doc.employee = emp.employee
            doc.company = self.company
            doc.attendance_date = self.posting_date
            
            doc.kegiatan_account = self.kegiatan_account

            doc.voucher_type = self.doctype
            doc.voucher_no = self.name

            doc.save()

    def create_journal_entry(self):
        if not (self.employee_payment_account and self.kegiatan_account):
            frappe.throw("Please Set Employee Payment Account and Kegiatan Account First")

        je = frappe.new_doc("Journal Entry")
        je.update({
            "company": self.company,
            "posting_date": self.posting_date,
        })
        
        total_payment = 0.0
        for emp in self.hasil_kerja:
            if not emp.amount:
                continue

            je.append("account", {
                "account": self.employee_payment_account,
                "party_type": "Employee",
                "party": emp.employee,
                "debit_in_account_currency": emp.amount
            })
            total_payment += emp.amount

        je.append("account", {
            "account": self.kegiatan_account,
            "debit_in_account_currency": total_payment
        })

        je.submit()

        self.db_set("journal_entry", je.name)
          
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

    def on_cancel(self):
        self.remove_journal()
        self.delete_payment_log()

        self.update_rkb_realization()

    def remove_journal(self):
        if not self.journal_entry:
            return
        
        doc = frappe.get_doc("Journal Entry", self.journal_entry)
        if doc.docstatus == 1:
            doc.cancel()

        self.db_set("journal_entry", "")
        doc.delete()
                
    def delete_payment_log(self):
        filters={"voucher_type": self.doctype, "voucher_no": self.name}
        for emp_log in frappe.get_all("Employee Payment Log", 
            filters=filters, pluck="name"
        ):
            frappe.delete_doc("Employee Payment Log", emp_log)

    def update_rkb_realization(self):
        frappe.get_doc(self.voucher_type, self.voucher_no).calculate_used_and_realized()