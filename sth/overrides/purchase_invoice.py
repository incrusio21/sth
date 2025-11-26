import frappe

@frappe.whitelist()
def get_all_training_event_by_supplier(supplier):
  events = frappe.get_all(
    "Training Event",
    filters={"supplier": supplier},
    fields=[
      "name",
      "custom_posting_date",
      "supplier",
    ],
    order_by="custom_posting_date desc"
  )

  return events

@frappe.whitelist()
def get_item_costing_in_training_events(training_events):
  training_events = frappe.parse_json(training_events)
  return frappe.db.sql("""
    SELECT
    tec.parent,
    tec.name,
    tec.expense_type,
    i.name as item,
    i.item_name as item_code,
    i.stock_uom as stock_uom,
    tec.total_amount
    FROM `tabTraining Event Costing` as tec
    JOIN `tabExpense Claim Type` as ect ON ect.name = tec.expense_type
    JOIN `tabItem` as i ON i.name = ect.custom_item
    WHERE tec.parent IN %(training_events)s;
  """, {"training_events": tuple(training_events)}, as_dict=True)