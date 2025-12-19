# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns(filters)
	res = get_result(filters)

	return columns, res

def get_result(filters):
	
	return frappe.db.sql(
		f"""
		select 
			po.unit, po.name as purchase_order, po.transaction_date, 
			po.supplier, kg.nm_kgt as kegiatan, poi.amount, po.currency, 
			(poi.received_qty*poi.rate) as realization_amount, (poi.received_qty/poi.qty*100) as realization,
			po.status
		from `tabPurchase Order` po
		left join `tabPurchase Order Item` poi on poi.parent = po.name 
		left join `tabKegiatan` kg on kg.name = poi.kegiatan 
		where po.docstatus = 1 {get_conditions(filters)}
	""",
		filters,
		as_dict=1,
	)

def get_conditions(filters):
	conditions = []

	if filters.get("transaction_date"):
		conditions.append("po.transaction_date = %(transaction_date)s")

	if filters.get("unit"):
		conditions.append("po.unit = %(unit)s")
	
	if filters.get("supplier"):
		conditions.append("po.supplier = %(supplier)s")

	if filters.get("kegiatan"):
		conditions.append("poi.kegiatan = %(kegiatan)s")

	return "and {}".format(" and ".join(conditions)) if conditions else ""
def get_columns(filters):
	
	columns = [
		{
			"label": _("Unit"),
			"fieldname": "unit",
			"fieldtype": "Link",
			"options": "Unit",
		},
		{
			"label": _("No Transaction"),
			"fieldname": "purchase_order",
			"fieldtype": "Link",
			"options": "Purchase Order",
		},
		{
			"label": _("Date"),
			"fieldname": "transaction_date",
			"fieldtype": "Date",
		},
		{
			"label": _("Blok"),
			"fieldname": "blok",
			"fieldtype": "Link",
			"options": "Blok",
		},
		{
			"label": _("Kegiatan"),
			"fieldname": "kegiatan",
			"fieldtype": "Data",
		},
		{
			"label": _("Supplier"),
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
		},
		{
			"label": _("Amount"),
			"fieldname": "amount",
			"fieldtype": "Currency",
			"options": "currency",
		},
		{
			"label": _("Currency"),
			"fieldname": "currency",
			"fieldtype": "Link",
			"options": "Currency",
		},
		{
			"label": _("Realization Amount"),
			"fieldname": "realization_amount",
			"fieldtype": "Currency",
			"options": "currency",
		},
		{
			"label": _("Realization"),
			"fieldname": "realization",
			"fieldtype": "Percent",
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
		},
	]

	return columns