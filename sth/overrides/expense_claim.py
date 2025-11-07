import frappe

@frappe.whitelist()
def get_travel_request_expenses(travel_request, company):
  return frappe.db.sql("""
    SELECT
    tr.name as custom_travel_request,
    tr.custom_posting_date as expense_date,
    trc.name as costing_expense,
    tr.custom_estimate_depart_date as custom_estimate_depart_date,
    tr.custom_estimate_arrival_date as custom_estimate_arrival_date,
    trc.expense_type,
    trc.total_amount as amount,
    trc.total_amount as sanctioned_amount,
    eca.default_account
    FROM `tabTravel Request` as tr
    JOIN `tabTravel Request Costing` as trc ON trc.parent = tr.name
    JOIN `tabExpense Claim Account` as eca ON eca.parent = trc.expense_type
    WHERE tr.name = %s AND eca.company = %s
  """, (travel_request, company), as_dict=True)

@frappe.whitelist()
def get_travel_request_costing(costing_name):
    doc = frappe.get_doc("Travel Request Costing", costing_name)
    return doc