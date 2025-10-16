# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils.data import flt

from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip

class SalarySlip(SalarySlip):
    def calculate_component_amounts(self, component_type):
        super().calculate_component_amounts(component_type)

        self.add_employee_payment(component_type)
	
    def add_employee_payment(self, component_type):
        for struct_row in self._salary_structure_doc.get(component_type, {"is_flexible_payment": 1}):
            acc_amount = frappe._dict(
                frappe.get_all(
                    "Employee Payment Log", 
                    filters={
                        "employee": self.employee,
                        "company": self.company,
                        "posting_date": ["between", [self.start_date, self.end_date]],
                        "salary_component": struct_row.salary_component
                    }, 
                    fields=["account", "sum(amount)"], 
                    group_by="account", as_list=1, debug=1
                )
            )

            total_amount = flt(sum(acc_amount.values()))
            self.update_component_row(struct_row, total_amount, component_type)

    def get_data_for_eval(self):
        """Returns data for evaluating formula"""
        data, default_data = super().get_data_for_eval()

        filters = { "company": data.company }
        data.natura_rate = default_data.natura_rate = frappe.get_value("Natura Price", {
            **filters, "valid_from": ["<=", self.end_date]}, "harga_beras", order_by="valid_from desc", debug=1) or 0

        data.natura_multiplier = default_data.natura_multiplier = frappe.get_value("Natura Multiplier", {
            **filters, "pkp": data.pkp, "employment_type": data.employment_type }, "multiplier") or 0

        return data, default_data