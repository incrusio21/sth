import frappe

def set_training_event_purchase_invoice(self, method):
  if self.custom_reference_doctype == "Training Event" and self.custom_reference_name:
    training_event = frappe.get_doc("Training Event", self.custom_reference_name)
    training_event.db_set("custom_purchase_invoice", self.name)