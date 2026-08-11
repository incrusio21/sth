# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.exceptions import DoesNotExistError
from frappe.query_builder.functions import Sum

from frappe.utils import get_first_day
from hrms.hr.doctype.attendance.attendance import DuplicateAttendanceError

from sth.controllers.plantation_controller import PlantationController

force_item_fields = (
	"rencana_kerja_harian",
	"voucher_type",
	"voucher_no"
)

# state workflow terakhir BKM. GL Entry baru dibuat saat dokumen mencapai state ini,
# bukan saat submit, karena nilai dokumen masih bisa berubah selama periode berjalan.
POSTED = "Posted"

class BukuKerjaMandorController(PlantationController):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plantation_setting_def = []
        self._bkm_name = ""
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
                "status": "status",
                "hari_kerja": True,
                "removed_if_zero": False,
            }
        ]

        self._clear_fields = []
        # kode_mandor, bukan mandor: field mandor menyimpan nilai mentah kiriman API
        # yang bisa berupa ID User sistem luar. Employee-nya ada di kode_mandor.
        #
        # mandor_type tetap "mandor" supaya Buku Kerja Mandor Premi yang sudah ada
        # tetap ketemu — kuncinya ikut nilai ini, bukan nama fieldnya
        self._mandor_dict = [{"fieldname": "kode_mandor", "mandor_type": "mandor"}]

    def validate(self):
        self.clear_fields()
        self.set_payroll_date()
                
        # self.get_rencana_kerja_harian()
        # self.validate_previous_document()
        self.get_employee_payment_account()
        super().validate()
        
        # self.validate_emp_hari_kerja()

    def calculate(self):
        self.get_plantation_setting()
        
        super().calculate()

    def clear_fields(self):
        for field in self._clear_fields:
            self.set(field, None)

    def set_payroll_date(self):
        # update fungsi ini jika ada aturan khusus untuk document
        self.payroll_date = self.posting_date

    def validate_emp_hari_kerja(self):
        emp_log = self.check_emp_hari_kerja(validate=True)

        for emp in self.hasil_kerja:
            already_used = emp_log.get(emp.employee) or 0
            if ((emp.hari_kerja or 0) + already_used) > 1:
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

    def validate_previous_document(self):
        from sth.controllers.prev_doc_validate import validate_previous_document

        validate_previous_document(self)

    def get_employee_payment_account(self):
        self.employee_payment_account = frappe.get_cached_value("Company", self.company, "employee_payment_account")

    def on_submit(self, update_realization=True):
        self.create_or_update_payment_log()
        self.create_or_update_mandor_premi()
        self.make_attendance()
        self.check_emp_hari_kerja()
        # if update_realization:
        #     self.update_rkb_realization()

    def create_or_update_payment_log(self, hasil_kerja_list=[], component_type=None):

        if self.get("is_kontanan") == 1:
            return

        removed_epl = []
        for emp in self.hasil_kerja:
            # check apakah ada list khusus untuk d update
            if hasil_kerja_list and emp.name not in hasil_kerja_list:
                continue

            for log_updater in self.payment_log_updater:
                # cukup update data untuk component type tertentu
                if component_type and log_updater["component_type"] not in component_type:
                    continue

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
                
                status_field = log_updater.get("status")
                # jika ada nilai atau kosong tapi tidak di hapus 
                if amount or not log_updater.get("removed_if_zero"):
                    doc.employee = emp.employee
                    doc.company = self.company
                    doc.posting_date = self.posting_date
                    doc.payroll_date = self.payroll_date

                    if status_field and emp.get(status_field):
                        doc.status = emp.get(status_field)

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
                        doc.account = emp.get(log_updater["target_account"]) or self.get(log_updater["target_account"])

                    doc.save()
                else:
                    # removed jika nilai kosong dan bukan document baru
                    if not is_new:
                        removed_epl.append(doc)
                
        # hapus epl yang tidak digunakan
        for r in removed_epl:
            r.delete()
    
    def create_or_update_mandor_premi(self):
        date = get_first_day(self.posting_date) #if self._mandor_premi_date_monthly else self.posting_date
        
        for d in self._mandor_dict:
            mandor = self.get(d["fieldname"])
            if not mandor:
                continue

            mandor_type = d.get("mandor_type") or d["fieldname"]

            bkm_mandor_creation_savepoint = "create_bkm_mandor"
            try:
                frappe.db.savepoint(bkm_mandor_creation_savepoint)
                bkm_obj = frappe.get_doc(
                    doctype="Buku Kerja Mandor Premi", 
                    employee=mandor, buku_kerja_mandor=self._bkm_name, company=self.company, posting_date=date,
                    mandor_type=mandor_type
                )
                bkm_obj.flags.ignore_permissions = 1
                bkm_obj.flags.transaction_employee = 1
                bkm_obj.insert()

            except frappe.UniqueValidationError:
                if frappe.message_log:
                    frappe.message_log.pop()
                frappe.db.rollback(save_point=bkm_mandor_creation_savepoint)  # preserve transaction in postgres
                
                bkm_obj = frappe.get_last_doc("Buku Kerja Mandor Premi", {
                    "employee": mandor,
                    "mandor_type": mandor_type,
                    "company": self.company, 
                    "posting_date": date,
                    "buku_kerja_mandor": self._bkm_name
                })
                bkm_obj.flags.transaction_employee = 1
                bkm_obj.save()

    def make_attendance(self):
        employee = self.hasil_kerja + self.get_mandor_details()
        print(employee)
        for emp in employee:
            attendance_detail = {
                "employee": emp.employee, "company": self.company, "attendance_date": self.posting_date
            }

            add_att = "add_attendance"
            try:
                print("nyoba")
                frappe.db.savepoint(add_att)
                attendance = frappe.get_doc({
                    "doctype": "Attendance",
                    "status": emp.attendance_status,
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
        super().on_cancel()
        # self.remove_journal()
        self.delete_payment_log()
        # if not frappe.flags.mass_delete_bkm:
        self.create_or_update_mandor_premi()
        # self.update_rkb_realization()
                
    def delete_payment_log(self):
        for epl in frappe.get_all(
            "Employee Payment Log", 
            filters={"voucher_type": self.doctype, "voucher_no": self.name}, 
            pluck="name"
        ):
            frappe.delete_doc("Employee Payment Log", epl, flags=frappe._dict(transaction_employee=True))

    def get_mandor_details(self):
        mandor_list = []
        for m in self._mandor_dict:
            mandor = self.get(m["fieldname"])
            if not mandor:
                continue

            m_dict = frappe._dict({
                "employee": mandor,
                "attendance_status": "Present"
            })
            
            mandor_list.append(m_dict)

        return mandor_list
    
    def update_rkb_realization(self):
        frappe.get_doc(self.voucher_type, self.voucher_no).calculate_used_and_realized()

    def get_workflow_state(self):
        """State workflow dokumen, atau None kalau doctype belum punya workflow aktif."""
        workflow = self.meta.get_workflow()
        if not workflow:
            return None

        fieldname = frappe.get_cached_value("Workflow", workflow, "workflow_state_field")

        return self.get(fieldname or "workflow_state")

    def is_posted(self):
        return self.get_workflow_state() == POSTED

    def allow_gl_entry(self):
        """
        Tanpa workflow aktif dokumen submitted langsung dianggap final (perilaku lama).
        Dengan workflow, GL Entry baru boleh dibuat setelah state Posted.
        """
        state = self.get_workflow_state()

        return state is None or state == POSTED

    def has_gl_entry(self):
        return bool(frappe.db.exists("GL Entry", {
            "voucher_type": self.doctype,
            "voucher_no": self.name,
            "is_cancelled": 0
        }))

    def make_gl_entry_on_submit(self):
        if self.allow_gl_entry():
            self.make_gl_entry()

    def on_update_after_submit(self):
        self.make_gl_entry_on_post()

    def make_gl_entry_on_post(self):
        """GL Entry dibuat sekali saat dokumen berpindah ke Posted."""
        if not self.is_posted() or self.has_gl_entry():
            return

        self.make_gl_entry()

    def set_as_posted(self):
        """
        Dipakai saat Accounting Period disubmit: dokumen yang masih Submitted
        dipindahkan ke Posted lalu GL Entry-nya dibuat.
        """
        if self.docstatus != 1 or self.is_posted():
            return False

        workflow = self.meta.get_workflow()
        if not workflow:
            return False

        fieldname = frappe.get_cached_value("Workflow", workflow, "workflow_state_field") or "workflow_state"
        self.db_set(fieldname, POSTED, update_modified=False)

        # alert per dokumen hanya jadi noise saat posting massal
        self.flags.no_gl_alert = True
        self.make_gl_entry_on_post()

        return True

    def show_gl_alert(self, message, indicator="green"):
        if self.flags.re_calculate or self.flags.no_gl_alert:
            return

        frappe.msgprint(message, indicator=indicator, alert=True)

    def repair_employee_payment_log(self):
        # cancelled tidak pernah dihitung ulang
        if self.docstatus > 1:
            return

        # dokumen Posted sudah masuk buku besar dan periodenya ditutup,
        # nilainya tidak boleh berubah lagi
        if self.is_posted():
            frappe.throw(
                _("{0} sudah Posted, upah dan premi tidak bisa dihitung ulang").format(frappe.bold(self.name))
            )

        is_submitted = self.docstatus == 1

        if is_submitted:
            self.delete_payment_log()

        self.flags.re_calculate = 1
        for hk in self.hasil_kerja:
            hk.amount = 0

        self.calculate()
        self.db_update_all()

        # draft belum punya Employee Payment Log, cukup perbarui nilai dokumennya.
        # log akan dibuat seperti biasa saat dokumen di-submit.
        if not is_submitted:
            return

        self.create_or_update_payment_log()
        self.create_or_update_mandor_premi()
        self.repair_gl_entry()

    def repair_gl_entry(self):
        # GL Entry lama diganti, bukan di-reverse, karena nilai dokumen memang
        # diperbaiki di tanggal yang sama. dokumen yang belum punya GL Entry
        # (belum Posted) tidak perlu disentuh.
        if not self.has_gl_entry():
            return

        self.delete_gl_entry()
        self.make_gl_entry()

    def delete_gl_entry(self):
        for gl in frappe.get_all(
            "GL Entry",
            filters={
                "voucher_type": self.doctype,
                "voucher_no": self.name,
                "is_cancelled": 0
            },
            pluck="name"
        ):
            # entry hasil reverse dari cancel sebelumnya sengaja tidak disentuh
            frappe.delete_doc("GL Entry", gl, ignore_permissions=True)