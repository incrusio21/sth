import frappe
from frappe import _
from frappe.utils import getdate

def set_training_event_purchase_invoice(self, method):
	if self.custom_reference_doctype == "Training Event" and self.custom_reference_name:
		training_event = frappe.get_doc("Training Event", self.custom_reference_name)
		training_event.db_set("custom_purchase_invoice", self.name)

@frappe.whitelist()
def get_default_coa(type,company):
	return frappe.get_value("Procurement Settings Account",{"company":company,"type":type},["account"])


def check_tanggal_kirim(self,method):
	 for item in doc.items:
			if item.purchase_receipt:
					# Get Purchase Receipt posting date
					pr_posting_date = frappe.db.get_value(
							'Purchase Receipt', 
							item.purchase_receipt, 
							'posting_date'
					)
					
					if pr_posting_date:
							pi_posting_date = getdate(doc.posting_date)
							pr_posting_date = getdate(pr_posting_date)
							
							if pi_posting_date < pr_posting_date:
									frappe.throw(
											_("Row {0}: Purchase Invoice posting date ({1}) cannot be before Purchase Receipt {2} posting date ({3})")
											.format(
													item.idx,
													frappe.format(pi_posting_date, {'fieldtype': 'Date'}),
													item.purchase_receipt,
													frappe.format(pr_posting_date, {'fieldtype': 'Date'})
											),
											title=_("Invalid Posting Date")
									)