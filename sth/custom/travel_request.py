import frappe

def create_employee_advance(self, method):
  company = frappe.get_doc("Company", self.company)
  account = frappe.get_doc("Account", company.default_receivable_account)
  employee = frappe.get_doc("Employee", self.employee)

  ea = frappe.new_doc("Employee Advance")
  ea.employee = self.employee
  ea.employee_name = self.employee_name
  ea.unit = employee.get("unit")
  ea.posting_date = self.custom_posting_date
  ea.company = self.company
  ea.purpose = self.purpose_of_travel
  ea.currency = account.account_currency
  ea.exchange_rate = 1
  ea.advance_amount = self.custom_grand_total_costing
  ea.advance_account = account.name
  ea.mode_of_payment = "Cash"

  ea.submit()
  self.db_set("custom_employee_advance", ea.name)

  # frappe.throw("custom create_employee_advance")
  
def cancel_employee_advance(self, method):
  ea = frappe.get_doc("Employee Advance", self.custom_employee_advance)
  ea.cancel()
  
  self.db_set("custom_employee_advance", "")
  # frappe.throw(self.custom_employee_advance)