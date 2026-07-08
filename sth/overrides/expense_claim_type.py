import frappe
from frappe import _
from hrms.hr.doctype.expense_claim_type.expense_claim_type import ExpenseClaimType

class ExpenseClaimType(ExpenseClaimType):
  def validate_repeating_companies(self):
    accounts_list = []

    for row in self.accounts:
      accounts_list.append((row.company, row.unit))

    if len(accounts_list) != len(set(accounts_list)):
      frappe.throw(_("Kombinasi Company dan Unit tidak boleh duplikat"))