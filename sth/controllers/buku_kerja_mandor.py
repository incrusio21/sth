# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.exceptions import DoesNotExistError
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
                "target_amount": "amount",
                "target_account": "kegiatan_account",
                "target_salary_component": "salary_component",
                "component_type": "Upah",
                "hari_kerja": True,
                "removed_if_zero": False,
            }
        ]

    def validate(self):
        self.set_payroll_date()
        
        self.get_plantation_setting()
        # self.get_rencana_kerja_harian()
        self.validate_hasil_kerja_harian()
        # self.validate_previous_document()
        self.get_employee_payment_account()
        super().validate()
        
        self.validate_emp_hari_kerja()
    
    def set_payroll_date(self):
        # update fungsi ini jika ada aturan khusus untuk document
        self.payroll_date = self.posting_date

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

        from sth.plantation import get_plantation_settings

        for key, fieldname in target_fields.items():
            self.set(fieldname, get_plantation_settings(key))

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
        self.check_emp_hari_kerja()

        # if update_realization:
        #     self.update_rkb_realization()

    def create_or_update_payment_log(self):
        # cek jika bkm memiliki field status
        status = self.meta.has_field("status")
        removed_epl = []
        for emp in self.hasil_kerja:
            for log_updater in self.payment_log_updater:
                is_new = False
                amount = emp.get(log_updater["target_amount"])
                try:
                    doc = frappe.get_last_doc("Employee Payment Log", {
                        "voucher_type": self.doctype,
                        "voucher_no": self.name,
                        "voucher_detail_no": emp.name,
                        "component_type": log_updater["component_type"]
                    })
                except DoesNotExistError:
                    is_new = True
                    doc = frappe.new_doc("Employee Payment Log")
                
                # jika ada nilai atau kosong tapi tidak di hapus 
                if amount or not log_updater.get("removed_if_zero"):
                    doc.employee = emp.employee
                    doc.company = self.company
                    doc.posting_date = self.posting_date
                    doc.payroll_date = self.payroll_date

                    doc.status = self.status if status else "Approved"

                    doc.hari_kerja = emp.hari_kerja if log_updater.get("hari_kerja") else 0
                    doc.amount = amount

                    # details
                    doc.voucher_type = self.doctype
                    doc.voucher_no = self.name
                    doc.voucher_detail_no = emp.name
                    doc.component_type = log_updater["component_type"]

                    doc.salary_component = self.get(log_updater["target_salary_component"])
                    doc.against_salary_component = self.get("against_salary_component")

                    if log_updater.get("target_account"):
                        doc.account = self.get(log_updater["target_account"])

                    doc.save()
                else:
                    # removed jika nilai kosong dan bukan document baru
                    if not is_new:
                        removed_epl.append(doc)
                
        self.update_child_table("hasil_kerja")

        # hapus epl yang tidak digunakan
        for r in removed_epl:
            r.delete()
          
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
                frappe.msgprint("Employee {} exceeds Hari Kerja".format(emp.employee))

    def on_cancel(self):
        # self.remove_journal()
        self.delete_payment_log()

        # self.update_rkb_realization()
                
    def delete_payment_log(self):
        for epl in frappe.get_all(
            "Employee Payment Log", 
            filters={"voucher_type": self.doctype, "voucher_no": self.name}, 
            pluck="name"
        ):
            frappe.delete_doc("Employee Payment Log", epl, flags=frappe._dict(transaction_employee=True))

    def update_rkb_realization(self):
        frappe.get_doc(self.voucher_type, self.voucher_no).calculate_used_and_realized()