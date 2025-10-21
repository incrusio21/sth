# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.query_builder.functions import Sum

from frappe.utils import get_link_to_form
from hrms.hr.doctype.attendance.attendance import DuplicateAttendanceError

from sth.controllers.plantation_controller import PlantationController

force_item_fields = (
	"rencana_kerja_harian",
	"voucher_type",
	"voucher_no"
)

class BukuKerjaMandorController(PlantationController):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plantation_setting_def = []
        
        self.fieldname_total.extend([
			"hari_kerja", "qty"
		])
        
        self.kegiatan_fetch_fieldname = ["account as kegiatan_account", "volume_basis", "rupiah_basis"]
        
        self.payment_log_updater = [
            {
                "target_link": "employee_payment_log",
                "target_amount": "amount",
                "target_account": "kegiatan_account",
                "target_salary_component": "salary_component",
                "hari_kerja": True,
                "removed_if_zero": False,
            }
        ]

    def validate(self):
        self.get_plantation_setting()
        # self.get_rencana_kerja_harian()
        self.validate_hasil_kerja_harian()
        # self.validate_previous_document()
        self.get_employee_payment_account()
        super().validate()
        
        self.validate_emp_hari_kerja()
    
    def validate_emp_hari_kerja(self):
        emp_log = self.check_emp_hari_kerja(validate=True)

        for emp in self.hasil_kerja:
            already_used = emp_log.get(emp.employee) or 0
            if (emp.hari_kerja + already_used) > 1:
                frappe.throw("Employee {} exceeds Hari Kerja".format(emp.employee))

    def get_plantation_setting(self):
        if not self.plantation_setting_def:
            return
        
        target_fields = {
            (ps[1] if isinstance(ps, list) else ps): (ps[0] if isinstance(ps, list) else ps)
            for ps in self.plantation_setting_def
        }

        plan_settings = frappe.db.get_value("Plantation Settings", None, list(target_fields), as_dict=1)
        if not plan_settings:
            frappe.throw("Please set data in {} first".format(get_link_to_form("Plantation Settings", "Plantation Settings")))

        for key, fieldname in target_fields.items():
            self.set(fieldname, plan_settings.get(key))

    def get_rencana_kerja_harian(self):
        from sth.controllers.queries import get_rencana_kerja_harian

        ret = get_rencana_kerja_harian(self.kegiatan, self.divisi, self.blok, self.posting_date)
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
        self.create_or_update_payment_log()
        # self.create_journal_entry()
        self.make_attendance()
        # self.check_emp_hari_kerja()

        # if update_realization:
        #     self.update_rkb_realization()

    def create_or_update_payment_log(self):
        # cek jika bkm memiliki field status
        status = self.meta.get_field("status")

        for emp in self.hasil_kerja:
            for log_updater in self.payment_log_updater:
                amount = emp.get(log_updater["target_amount"])
                if target_key := emp.get(log_updater["target_link"]):
                    doc = frappe.get_doc("Employee Payment Log", target_key)
                else:
                    if log_updater.get("removed_if_zero") and not amount:
                        continue

                    doc = frappe.new_doc("Employee Payment Log")

                doc.employee = emp.employee
                doc.company = self.company
                doc.posting_date = self.posting_date
                
                doc.status = self.status if status else "Approved"

                doc.hari_kerja = emp.hari_kerja if log_updater.get("hari_kerja") else 0
                doc.amount = amount

                doc.salary_component = self.get(log_updater["target_salary_component"])
                
                if log_updater.get("target_account"):
                    doc.account = self.get(log_updater["target_account"])

                doc.save()

                emp.set(log_updater["target_link"], doc.name)

        self.update_child_table("hasil_kerja")

    # def create_journal_entry(self):
    #     if not (self.salary_component and self.kegiatan_account):
    #         frappe.throw("Please Set Salary Component and Kegiatan Account First")

    #     je = frappe.new_doc("Journal Entry")
    #     je.update({
    #         "company": self.company,
    #         "posting_date": self.posting_date,
    #     })

    #     total_payment = {}
    #     for je_updater in self.payment_log_updater:
    #         for emp in self.hasil_kerja:
    #             amount = emp.get(je_updater["target_amount"])
    #             if not amount:
    #                 continue
                
    #             total_payment.setdefault(je_updater["target_link"], {
    #                 "salary_component":
    #                 "biaya_kebun":
    #             })
    #             je.append("accounts", {
    #                 "account": self.employee_payment_account,
    #                 "party_type": "Employee",
    #                 "party": emp.employee,
    #                 "debit_in_account_currency": emp.amount
    #             })

    #             total_payment += emp.amount

    #     je.append("accounts", {
    #         "account": self.kegiatan_account,
    #         "credit_in_account_currency": total_payment
    #     })

    #     je.submit()

    #     self.db_set("journal_entry", je.name)
          
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

    def check_emp_hari_kerja(self, validate=False):
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
        ).run(as_dict=not validate)

        if validate:
            return frappe._dict(employee_hk)
        
        for emp in employee_hk:
            if emp.hari_kerja > 1:
                frappe.throw("Employee {} exceeds Hari Kerja".format(emp.employee))

    def on_cancel(self):
        # self.remove_journal()
        self.delete_payment_log()

        # self.update_rkb_realization()

    # def remove_journal(self):
    #     if not self.journal_entry:
    #         return
        
    #     doc = frappe.get_doc("Journal Entry", self.journal_entry)
    #     if doc.docstatus == 1:
    #         doc.cancel()

    #     self.db_set("journal_entry", "")
    #     doc.delete()
                
    def delete_payment_log(self):
        for emp in self.hasil_kerja:
            for log_updater in self.payment_log_updater:
                value = emp.get(log_updater["target_link"])
                if not value:
                    continue
                
                emp.db_set(log_updater["target_link"], "")
                frappe.delete_doc("Employee Payment Log", value)

        filters={"voucher_type": self.doctype, "voucher_no": self.name}
        for emp_log in frappe.get_all("Employee Payment Log", 
            filters=filters, pluck="name"
        ):
            frappe.delete_doc("Employee Payment Log", emp_log)

    def update_rkb_realization(self):
        frappe.get_doc(self.voucher_type, self.voucher_no).calculate_used_and_realized()