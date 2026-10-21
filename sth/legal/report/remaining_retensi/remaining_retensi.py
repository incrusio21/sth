# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns(filters)
	res = get_result(filters)
	return columns, res

def get_result(filters):
	
	# Retensi yang dipotong lewat baris taxes __from_retensi__ (tax_amount minus)
	# sudah pindah ke akun retensi, jadi tidak lagi ditahan di outstanding.
	# Sama dengan retensi_ditahan() di overrides/purchase_invoice.py.
	return frappe.db.sql(
		"""
		select
			name as purchase_invoice,
			posting_date,
			supplier,
			least(
				outstanding_amount,
				retensi_amount + ifnull((
					select sum(t.tax_amount) from `tabPurchase Taxes and Charges` t
					where t.parent = `tabPurchase Invoice`.name
						and t.parenttype = 'Purchase Invoice'
						and t.description = '__from_retensi__'
				), 0)
			) as rem_retensi
		from `tabPurchase Invoice`
		where 
			company = %(company)s and 
			retensi_amount > 0 and
			docstatus = 1 {}
		HAVING rem_retensi > 0
	""".format(
		get_conditions(filters)
	),
		filters,
		as_dict=1,
	)

def get_conditions(filters):
	conditions = []

	if filters.get("posting_date"):
		conditions.append("posting_date = %(posting_date)s")
	
	if filters.get("unit"):
		conditions.append("unit = %(unit)s")

	if filters.get("supplier"):
		conditions.append("supplier = %(supplier)s")

	return "and {}".format(" and ".join(conditions)) if conditions else ""

def get_columns(filters):
	
	columns = [
		{
			"label": _("No Transaction"),
			"fieldname": "purchase_invoice",
			"fieldtype": "Link",
			"options": "Purchase Invoice",
		},
		{
			"label": _("Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
		},
		{
			"label": _("Supplier"),
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
		},
		{
			"label": _("Remaining Retensi"),
			"fieldname": "rem_retensi",
			"fieldtype": "Currency",
			"options": "currency",
		},
	]

	return columns