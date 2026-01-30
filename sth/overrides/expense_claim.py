import frappe
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt
from frappe import _
from hrms.hr.doctype.expense_claim.expense_claim import ExpenseClaim

class ExpenseClaim(ExpenseClaim):
	def validate_advances(self):
		self.total_advance_amount = 0

		for d in self.get("advances"):
			self.round_floats_in(d)

			ref_doc = frappe.db.get_value(
				"Employee Advance",
				d.employee_advance,
				["posting_date", "paid_amount", "claimed_amount", "return_amount", "advance_account"],
				as_dict=1,
			)
			d.posting_date = ref_doc.posting_date
			d.advance_account = ref_doc.advance_account
			d.advance_paid = ref_doc.paid_amount
			d.unclaimed_amount = flt(ref_doc.paid_amount) - flt(ref_doc.claimed_amount)

			# if d.allocated_amount and flt(d.allocated_amount) > (
			# 	flt(d.unclaimed_amount) - flt(d.return_amount)
			# ):
			# 	frappe.throw(
			# 		_("Row {0}# Allocated amount {1} cannot be greater than unclaimed amount {2}").format(
			# 			d.idx, d.allocated_amount, d.unclaimed_amount
			# 		)
			# 	)

			self.total_advance_amount += flt(d.allocated_amount)

		if self.total_advance_amount:
			self.round_floats_in(self, ["total_advance_amount"])
			precision = self.precision("total_advance_amount")
			amount_with_taxes = flt(
				(flt(self.total_sanctioned_amount, precision) + flt(self.total_taxes_and_charges, precision)),
				precision,
			)

			if flt(self.total_advance_amount, precision) > amount_with_taxes:
				frappe.throw(_("Total advance amount cannot be greater than total sanctioned amount"))

	def validate_sanctioned_amount(self):
			return
		# for d in self.get("expenses"):
			# if flt(d.sanctioned_amount) > flt(d.amount):
			# 	frappe.throw(
			# 		_("Sanctioned Amount cannot be greater than Claim Amount in Row {0}.").format(d.idx)
			# 	)

	def calculate_total_amount(self):
		self.total_claimed_amount = 0
		self.total_sanctioned_amount = 0

		for d in self.get("expenses"):
			self.round_floats_in(d)

			if self.approval_status == "Rejected":
				d.sanctioned_amount = 0.0

			self.total_claimed_amount += flt(d.amount)
			self.total_sanctioned_amount += flt(d.sanctioned_amount)

		tsa = self.total_sanctioned_amount or 0
		tca = self.total_claimed_amount or 0

		if tsa < tca:
			self.status_selisih = "Kurang Bayar"
		elif tsa > tca:
			self.status_selisih = "Lebih Bayar"
		else:
			self.status_selisih = "Tidak Ada Selisih"

		self.total_selisih = abs(self.total_claimed_amount - self.total_sanctioned_amount)
		self.round_floats_in(self, ["total_claimed_amount", "total_sanctioned_amount"])

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