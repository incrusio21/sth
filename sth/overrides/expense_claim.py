import frappe
from frappe.model.mapper import get_mapped_doc

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

@frappe.whitelist()
def make_purchase_invoice_from_expense_claim(source_name, target_doc=None):

    def set_missing_values(source, target):
        target.billing_address = None
        target.set_missing_values()
        target.calculate_taxes_and_totals()

    def map_item(source_doc, target_doc, source_parent):
        target_doc.qty = 1
        target_doc.rate = source_doc.sanctioned_amount
        target_doc.amount = source_doc.sanctioned_amount
        target_doc.cost_center = source_doc.cost_center

    doclist = get_mapped_doc(
        "Expense Claim",
        source_name,
        {
            "Expense Claim": {
                "doctype": "Purchase Invoice",
                "field_map": {
                    "posting_date": "posting_date",
                    "company": "company",
                },
                "postprocess": lambda source, target: set_missing_values(source, target),
            },
            "Expense Claim Detail": {
                "doctype": "Purchase Invoice Item",
                "field_map": {
                    "description": "description",
                    "expense_type": "item_name",
                    "sanctioned_amount": "amount",
                },
                "postprocess": map_item,
            },
        },
        target_doc,
    )

    default_supplier = "Employee Claims"

    if not frappe.db.exists("Supplier", default_supplier):
        frappe.throw(f"Supplier '{default_supplier}' does not exist. Please create it first.")

    doclist.supplier = default_supplier

    return doclist