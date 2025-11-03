# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import json

import frappe
from frappe.utils import date_diff, flt, month_diff, now
from frappe.query_builder.functions import IfNull

from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip, get_salary_component_data
from hrms.payroll.doctype.payroll_period.payroll_period import (
	get_period_factor,
)
from hrms.payroll.doctype.salary_slip.salary_slip_loan_utils import (\
	set_loan_repayment,
)

class SalarySlip(SalarySlip):
    def on_submit(self):
        super().on_submit()
        self.update_payment_related("Employee Payment Log", "payment_log_list")
        self.update_payment_related("Loan Repayment", "loan_repayment_list")

    def on_cancel(self):
        super().on_submit()

        self.update_payment_related("Employee Payment Log", "payment_log_list", cancel=1)
        self.update_payment_related("Loan Repayment", "loan_repayment_list", cancel=1)

    def update_payment_related(self, doctype, list_field, cancel=0):
        dt = frappe.qb.DocType(doctype)

        query = (
            frappe.qb.update(dt)
            .set(dt.is_paid, 0 if cancel else 1)
            .set(dt.salary_slip, "" if cancel else self.name)
            .set(dt.modified, now())
            .set(dt.modified_by, frappe.session.user)
            .where(
                (dt.salary_slip == self.name) if cancel
                else (dt.name.isin(getattr(self, list_field)))
            )
        )

        query.run()

    def calculate_net_pay(self, skip_tax_breakup_computation: bool = False):
        # agar payment log selalu generate ulang
        self.payment_log_list = []
        self.loan_repayment_list = []
        self._against_employee_payment = {}

        def set_gross_pay_and_base_gross_pay():
            self.gross_pay = self.get_component_totals("earnings", depends_on_payment_days=1)
            self.base_gross_pay = flt(
                flt(self.gross_pay) * flt(self.exchange_rate), self.precision("base_gross_pay")
            )

        if self.salary_structure:
            self.calculate_component_amounts("earnings")

        # get remaining numbers of sub-period (period for which one salary is processed)
        if self.payroll_period:
            self.remaining_sub_periods = get_period_factor(
                self.employee,
                self.start_date,
                self.end_date,
                self.payroll_frequency,
                self.payroll_period,
                joining_date=self.joining_date,
                relieving_date=self.relieving_date,
            )[1]

        set_gross_pay_and_base_gross_pay()

        if self.salary_structure:
            self.calculate_component_amounts("deductions")

        self.calculate_against_employee_payment()

        set_loan_repayment(self)

        self.calculate_subsidy_loan()
        
        self.set_precision_for_component_amounts()
        self.set_net_pay()
        if not skip_tax_breakup_computation:
            self.compute_income_tax_breakup()

    def calculate_against_employee_payment(self):
        # hapus component against terlebih dahulu 
        self.remove_against_employee_payment()

        for component, total_amount in self._against_employee_payment.items():
            component_type = "earnings" if total_amount > 0 else "deductions"
            self.add_component_custom(component, component_type, abs(total_amount))

    def remove_against_employee_payment(self):
        removed_component = []
        for component_type in ["earnings", "deductions"]:
            removed_component.extend(self.get(component_type, {"against_employee_payment": 1}))
        
        for d in removed_component:
            self.remove(d)

    def add_structure_components(self, component_type):
        self.data, self.default_data = self.get_data_for_eval()

        for struct_row in self._salary_structure_doc.get(component_type):
            if not struct_row.is_flexible_payment:
                self.add_structure_component(struct_row, component_type)
            else:
                self.add_employee_payment(struct_row, component_type)

    def add_employee_payment(self, struct_row, component_type):
        epl = frappe.qb.DocType("Employee Payment Log")

        emp_pl = (
            frappe.qb.from_(epl)
            .select(epl.name, epl.account, epl.against_salary_component, epl.amount, epl.status)
            .where(
                (epl.employee == self.employee)
                & (epl.company == self.company)
                & (epl.payroll_date.between(self.start_date, self.end_date))
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

            if pl.status != "Approved":
                frappe.throw("There are still Payment Logs for Employee {} that have not been Approved".format(self.employee))

            if pl.against_salary_component:
                key = pl.against_salary_component
                self._against_employee_payment[key] = self._against_employee_payment.get(key, 0) + (
                    pl.amount if component_type == "deductions" else -pl.amount
                )

            self.payment_log_list.append(pl.name)

        struct_row.account_rate = json.dumps(account_total)

        # default behavior, the system does not add if component amount is zero
        # if remove_if_zero_valued is unchecked, then ask system to add component row
        remove_if_zero_valued = frappe.get_cached_value(
            "Salary Component", struct_row.salary_component, "remove_if_zero_valued"
        )

        self.update_component_row(
            struct_row, 
            flt(total_amount), 
            component_type,
            remove_if_zero_valued=remove_if_zero_valued,
        )

    def calculate_subsidy_loan(self):
        self.add_repaymant_subsidy()
        if self.get("loans"):
            self.add_loans_monthly_subsidy()

    def add_repaymant_subsidy(self):
        lp = frappe.qb.DocType("Loan Repayment")

        query = (
            frappe.qb.from_(lp)
            .select(lp.name, lp.subsidy_component, lp.against_subsidy_component, lp.amount_paid)
            .where(
                (IfNull(lp.subsidy_component, "") != "")
                & (lp.docstatus == 1)
                & (lp.is_paid == 0)
                & (lp.posting_date <= self.end_date)
            )
            .for_update()
        )

        subsidy_list = query.run(as_dict=True)

        subsidy_component, against_component = {}, {}

        for sc in subsidy_list:
            subsidy_component.setdefault(sc.subsidy_component, 0)
            against_component.setdefault(sc.against_subsidy_component, 0)

            subsidy_component[sc.subsidy_component] += sc.amount_paid
            against_component[sc.against_subsidy_component] += sc.amount_paid
            
            self.loan_repayment_list.append(sc.name)

        for component, total_amount in subsidy_component.items():
            self.add_component_custom(component, "earnings", total_amount)

        for component, total_amount in against_component.items():
            self.add_component_custom(component, "deductions", total_amount)
        
    def add_loans_monthly_subsidy(self):
        if self.payroll_frequency != "Monthly":
            return
        
        monthly_subsidy = {}
        for l in self.loans:
            if not l.monthly_subsidy_component:
                continue

            monthly_subsidy.setdefault(l.monthly_subsidy_component, 0)
            diff = month_diff(self.end_date, l.repayment_start_date) - 1
            
            subsidy_amount = frappe.get_value('Monthly Subsidy', 
                {"from_month": ["<=", diff], "to_month": [">=", diff], "parent": l.loan},
                "subsidy_amount"
            ) or 0

            monthly_subsidy[l.monthly_subsidy_component] += subsidy_amount

        for component, total_amount in monthly_subsidy.items():
            self.add_component_custom(component, "earnings", total_amount)

    def add_component_custom(self, component, component_type, total_amount):
        struct_row = get_salary_component_data(component)
        struct_row.against_employee_payment = 1

        self.update_component_row(
            struct_row, 
            flt(total_amount), 
            component_type,
            remove_if_zero_valued=True
        )

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
                "is_flexible_payment",
                "against_employee_payment",
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

        company = frappe.get_cached_doc("Company", self.company).as_dict()

        filters = { "company": self.company }
        data.natura_rate = default_data.natura_rate = frappe.get_value("Natura Price", {
            **filters, "valid_from": ["<=", self.end_date]}, "harga_beras", order_by="valid_from desc") or 0

        data.natura_multiplier = default_data.natura_multiplier = frappe.get_value("Natura Multiplier", {
            **filters, "pkp": data.pkp, "employment_type": data.employment_type }, "multiplier") or 0

        data.ump_harian = default_data.ump_harian = company.custom_ump_harian
        
        start_date = data.date_of_joining if date_diff(data.date_of_joining, self.start_date) > 0 else self.start_date
        end_date = data.contract_end_date if data.get("contract_end_date") \
            and date_diff(data.contract_end_date, self.end_date) < 0 else self.end_date

        data.total_holidays = default_data.total_holidays = len(self.get_holidays_for_employee(start_date , end_date))

        return data, default_data