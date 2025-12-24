# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from sth.hr_customize import get_premi_attendance_settings

class Attendance:
    def __init__(self, doc, method):
        self.doc = doc
        self.method = method

        match self.method:
            case "validate":
                self.validate_attendance_is_holiday()
                self.validate_premi_amount_and_component()
                self.validate_status_code()
            case "repair_employee_payment_log":
                self.delete_payment_log()

                self.validate_attendance_is_holiday()
                self.validate_premi_amount_and_component()
                self.doc.db_update()

                self.create_or_update_payment_log()
            case "on_submit":
                self.create_or_update_payment_log()
            case "on_cancel":
                self.delete_payment_log()

    def validate_status_code(self):
        if self.doc.status == "Present":
            self.doc.status_code = "H"
        elif self.doc.status == "On Leave":
            self.doc.status_code = frappe.get_value("Leave Type", self.doc.leave_type, "status_code")
        elif self.doc.status == "Absent":
            self.doc.status_code = "M"

    def validate_attendance_is_holiday(self):
        self.doc.is_holiday = 0
        if frappe.db.exists("Holiday", {"parent": self.doc.holiday_list, "holiday_date": self.doc.attendance_date}):
            self.doc.is_holiday = 1
    
    def validate_premi_amount_and_component(self):
        if self.doc.status not in ("Present"):
            return
            
        designation = frappe.get_cached_doc("Designation", self.doc.designation)
        self.doc.premi_amount = 0

        # set nilai premi dan tipe apa saja yang bisa di dapatkan
        pt = "Hari Biasa" if not self.doc.is_holiday else "Hari Libur"
        for premi in designation.premi:
            if premi.company == self.doc.company and premi.premi_type != pt:
                continue
            
            self.doc.salary_component = premi.salary_component \
                or get_premi_attendance_settings(premi.premi_type) \
                or designation.salary_component
            self.doc.premi_amount = premi.amount or 0
            
    def create_or_update_payment_log(self):
        doc = frappe.new_doc("Employee Payment Log")
        
        if self.doc.premi_amount:
            # jika ada nilai atau kosong tapi tidak di hapus 
            doc.employee = self.doc.employee
            doc.company = self.doc.company
            doc.posting_date = self.doc.attendance_date
            doc.payroll_date = self.doc.attendance_date

            doc.amount = self.doc.premi_amount
            
            doc.salary_component = self.doc.salary_component

            doc.voucher_type = self.doc.doctype
            doc.voucher_no = self.doc.name

            doc.save()

    def delete_payment_log(self):
        for epl in frappe.get_all(
            "Employee Payment Log", 
            filters={"voucher_type": self.doc.doctype, "voucher_no": self.doc.name}, 
            pluck="name"
        ):
            frappe.delete_doc("Employee Payment Log", epl, flags=frappe._dict(transaction_employee=True))

def debug_attendance():
    list_at = frappe.db.sql(""" SELECT name FROM `tabAttendance` """)
    for row in list_at:
        self = frappe.get_doc("Attendance", row[0])
        if self.status == "Present":
            self.status_code = "H"
        elif self.status == "On Leave":
            self.status_code = frappe.get_value("Leave Type", self.leave_type, "status_code")
        elif self.status == "Absent":
            self.status_code = "M"
        self.db_update()