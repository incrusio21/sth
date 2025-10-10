import frappe
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip

class SalarySlip(SalarySlip):
    def get_data_for_eval(self):
        """Returns data for evaluating formula"""
        data, default_data = super().get_data_for_eval()

        filters = { "company": data.company }
        data.natura_rate = default_data.natura_rate = frappe.get_value("Natura Price", {
            **filters, "valid_from": ["<=", self.end_date]}, "harga_beras", order_by="valid_from desc", debug=1) or 0

        data.natura_multiplier = default_data.natura_multiplier = frappe.get_value("Natura Multiplier", {
            **filters, "pkp": data.pkp, "employment_type": data.employment_type }, "multiplier") or 0

        return data, default_data