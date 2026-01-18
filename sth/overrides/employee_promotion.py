# Copyright (c) 2026, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _

from frappe.utils import getdate

from hrms.hr.doctype.employee_promotion.employee_promotion import EmployeePromotion
from sth.hr_customize.doctype.employee_update_log.employee_update_log import create_or_update_employee_propertry

class STHEmployeePromotion(EmployeePromotion):
    def before_submit(self):
        pass

    def on_submit(self):
        create_or_update_employee_propertry(self, self.promotion_date)
        # employee = frappe.get_doc("Employee", self.employee)
        # employee = update_employee_work_history(employee, self.promotion_details, date=self.promotion_date)

        # if self.revised_ctc:
        #     employee.ctc = self.revised_ctc

        # employee.save()

    def on_cancel(self):
        for emp_log in frappe.get_all("Employee Update Log", filters={
            "voucher_type": self.doctype,
            "voucher_no": self.name
        }, pluck="name"):
            frappe.delete_doc("Employee Update Log", emp_log)
            
        # employee = frappe.get_doc("Employee", self.employee)
        # employee = update_employee_work_history(employee, self.promotion_details, cancel=True)

        # if self.revised_ctc:
        #     employee.ctc = self.current_ctc

        # employee.save()