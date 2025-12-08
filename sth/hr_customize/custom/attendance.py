# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe

class Attendance:
    def __init__(self, doc, method):
        self.doc = doc
        self.method = method

        match self.method:
            case "validate":
                self.validate_attendance_is_holiday()
                self.validate_premi_amount_and_component()
            case "on_submit":
                self.create_or_update_payment_log()
            case "on_cancel":
                self.delete_payment_log()

    def validate_attendance_is_holiday(self):
        self.is_holiday = 0
        if frappe.db.exists("Holiday", {"parent": self.doc.holiday_list, "holiday_date": self.doc.attendance_date}):
            self.is_holiday = 1
    
    def validate_premi_amount_and_component(self):
        if self.doc.status not in ("Present"):
            return
            
        designation = frappe.get_cached_doc("Designation", self.doc.designation)
        self.doc.salary_component = designation.salary_component
        self.doc.premi_amount = 0

        # set nilai premi dan tipe apa saja yang bisa di dapatkan
        pt = ["Hari Biasa" if not self.doc.is_holiday else "Hari Libur"]
        # menentukan attendance merupakan tutup buku masih belum ada
        for premi in designation.premi:
            if premi.company == self.doc.company and premi.premi_type not in pt:
                continue
            
            self.doc.premi_amount += premi.amount or 0
            
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
            filters={"voucher_type": self.doctype, "voucher_no": self.name}, 
            pluck="name"
        ):
            frappe.delete_doc("Employee Payment Log", epl, flags=frappe._dict(transaction_employee=True))