# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import json

import frappe
from frappe.utils import flt, now

from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip

class SalarySlip(SalarySlip):
    def on_submit(self):
        super().on_submit()
        self.update_emp_payment_log()

    def on_cancel(self):
        super().on_submit()
        self.update_emp_payment_log(cancel=1)

    def update_emp_payment_log(self, cancel=0):
        epl = frappe.qb.DocType("Employee Payment Log")

        query = (
            frappe.qb.update(epl)
            .set(epl.is_paid, 0 if cancel else 1)
            .set(epl.salary_slip, "" if cancel else self.name)
            .set(epl.modified, now())
            .set(epl.modified_by, frappe.session.user)
            .where(
                (epl.salary_slip == self.name) if cancel
                else (epl.name.isin(self.payment_log_list))
            )
        )

        query.run()

    def calculate_net_pay(self, skip_tax_breakup_computation: bool = False):
        # agar payment log selalu generate ulang
        self.payment_log_list = []
        
        super().calculate_net_pay(skip_tax_breakup_computation)

    def calculate_component_amounts(self, component_type):
        super().calculate_component_amounts(component_type)

        self.add_employee_payment(component_type)

	
    def add_employee_payment(self, component_type):
        for struct_row in self._salary_structure_doc.get(component_type, {"is_flexible_payment": 1}):
            epl = frappe.qb.DocType("Employee Payment Log")

            emp_pl = (
                frappe.qb.from_(epl)
                .select(epl.name, epl.account, epl.amount)
                .where(
                    (epl.employee == self.employee)
                    & (epl.company == self.company)
                    & (epl.posting_date.between(self.start_date, self.end_date))
                    & (epl.salary_component == struct_row.salary_component)
                    & (epl.is_paid != 1)
                )
                .for_update()
            ).run(as_dict=1)

            account_total = {}
            total_amount = 0.0
            for pl in emp_pl:
                if pl.account:
                    account_total.setdefault(pl.account, 0)                    
                    account_total[pl.account] += pl.amount

                total_amount += pl.amount
                
                self.payment_log_list.append(pl.name)

            struct_row.account_rate = json.dumps(account_total)
            self.update_component_row(struct_row, flt(total_amount), component_type)

    def update_component_row(
		self,
		component_data,
		amount,
		component_type,
		additional_salary=None,
		is_recurring=0,
		data=None,
		default_amount=None,
		remove_if_zero_valued=None,
	):
        component_row = None
        for d in self.get(component_type):
            if d.salary_component != component_data.salary_component:
                continue

            if (not d.additional_salary and (not additional_salary or additional_salary.overwrite)) or (
                additional_salary and additional_salary.name == d.additional_salary
            ):
                component_row = d
                break

        if additional_salary and additional_salary.overwrite:
            # Additional Salary with overwrite checked, remove default rows of same component
            self.set(
                component_type,
                [
                    d
                    for d in self.get(component_type)
                    if d.salary_component != component_data.salary_component
                    or (d.additional_salary and additional_salary.name != d.additional_salary)
                    or d == component_row
                ],
            )

        if not component_row:
            if not (amount or default_amount) and remove_if_zero_valued:
                return

            component_row = self.append(component_type)
            for attr in (
                "depends_on_payment_days",
                "salary_component",
                "abbr",
                "do_not_include_in_total",
                "is_tax_applicable",
                "is_flexible_benefit",
                "variable_based_on_taxable_salary",
                "exempted_from_income_tax",
            ):
                component_row.set(attr, component_data.get(attr))

        if additional_salary:
            if additional_salary.overwrite:
                component_row.additional_amount = flt(
                    flt(amount) - flt(component_row.get("default_amount", 0)),
                    component_row.precision("additional_amount"),
                )
            else:
                component_row.default_amount = 0
                component_row.additional_amount = amount

            component_row.is_recurring_additional_salary = is_recurring
            component_row.additional_salary = additional_salary.name
            component_row.deduct_full_tax_on_selected_payroll_date = (
                additional_salary.deduct_full_tax_on_selected_payroll_date
            )
        else:
            component_row.default_amount = default_amount or amount
            component_row.additional_amount = 0
            component_row.deduct_full_tax_on_selected_payroll_date = (
                component_data.deduct_full_tax_on_selected_payroll_date
            )

        component_row.amount = amount
        component_row.account_list_rate = component_data.get("account_rate") or "{}"

        self.update_component_amount_based_on_payment_days(component_row, remove_if_zero_valued)

        if data:
            data[component_row.abbr] = component_row.amount
			
    def get_data_for_eval(self):
        """Returns data for evaluating formula"""
        data, default_data = super().get_data_for_eval()

        filters = { "company": data.company }
        data.natura_rate = default_data.natura_rate = frappe.get_value("Natura Price", {
            **filters, "valid_from": ["<=", self.end_date]}, "harga_beras", order_by="valid_from desc") or 0

        data.natura_multiplier = default_data.natura_multiplier = frappe.get_value("Natura Multiplier", {
            **filters, "pkp": data.pkp, "employment_type": data.employment_type }, "multiplier") or 0

        return data, default_data