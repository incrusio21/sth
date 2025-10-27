# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import json

import frappe
from frappe.utils import flt
from hrms.payroll.doctype.payroll_entry.payroll_entry import PayrollEntry

class PayrollEntry(PayrollEntry):
    
    def get_salary_components(self, component_type):
        salary_slips = self.get_sal_slip_list(ss_status=1, as_dict=True)

        if salary_slips:
            ss = frappe.qb.DocType("Salary Slip")
            ssd = frappe.qb.DocType("Salary Detail")
            salary_components = (
                frappe.qb.from_(ss)
                .join(ssd)
                .on(ss.name == ssd.parent)
                .select(
                    ssd.salary_component,
                    ssd.amount,
                    ssd.parentfield,
                    ssd.additional_salary,
                    ssd.account_list_rate,
                    ss.salary_structure,
                    ss.employee,
                )
                .where((ssd.parentfield == component_type) & (ss.name.isin([d.name for d in salary_slips])))
            ).run(as_dict=True)

            return salary_components
          
    def get_salary_component_total(
        self,
        component_type=None,
        employee_wise_accounting_enabled=False,
    ):
        salary_components = self.get_salary_components(component_type)
        if salary_components:
            component_dict = {}
            account_dict = {}

            for item in salary_components:
                if not self.should_add_component_to_accrual_jv(component_type, item):
                    continue
                
                employee_cost_centers = self.get_payroll_cost_centers_for_employee(
                    item.employee, item.salary_structure
                )
                employee_advance = self.get_advance_deduction(component_type, item)

                for cost_center, percentage in employee_cost_centers.items():

                    acc_dict = json.loads(item.account_list_rate)
                    for acc, value in acc_dict.items():
                        accounting_key = (acc, cost_center)
                        acc_against_cost_center = flt(value) * percentage / 100
                        account_dict[accounting_key] = account_dict.get(accounting_key, 0) + acc_against_cost_center

                        item.amount -= acc_against_cost_center

                    if not item.amount:
                        continue

                    amount_against_cost_center = flt(item.amount) * percentage / 100
                    
                    if employee_advance:
                        self.add_advance_deduction_entry(
                            item, amount_against_cost_center, cost_center, employee_advance
                        )
                    else:
                        key = (item.salary_component, cost_center)
                        component_dict[key] = component_dict.get(key, 0) + amount_against_cost_center

                    if employee_wise_accounting_enabled:
                        self.set_employee_based_payroll_payable_entries(
                            component_type, item.employee, amount_against_cost_center
                        )

            account_details = self.get_account(account_dict, component_dict=component_dict)

            return account_details 
        
    def get_account(self, account_dict, component_dict=None):
        for key, amount in component_dict.items():
            component, cost_center = key
            account = self.get_salary_component_account(component)
            accounting_key = (account, cost_center)

            account_dict[accounting_key] = account_dict.get(accounting_key, 0) + amount

        return account_dict