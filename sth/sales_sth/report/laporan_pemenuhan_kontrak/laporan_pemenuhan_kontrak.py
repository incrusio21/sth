import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	return [
		{
			"fieldname": "so_no",
			"label": _("SO No"),
			"fieldtype": "Link",
			"options": "Sales Order",
			"width": 200
		},
		{
			"fieldname": "item_code",
			"label": _("Item Code"),
			"fieldtype": "Link",
			"options": "Item",
			"width": 250
		},
		{
			"fieldname": "item_name",
			"label": _("Item Name"),
			"fieldtype": "Data",
			"width": 200
		},
		{
			"fieldname": "qty_in_so",
			"label": _("Qty in SO"),
			"fieldtype": "Float",
			"width": 120
		},
		{
			"fieldname": "qty_in_dn",
			"label": _("Qty in DN"),
			"fieldtype": "Float",
			"width": 120
		},
		{
			"fieldname": "outstanding",
			"label": _("Outstanding"),
			"fieldtype": "Float",
			"width": 120
		},
		{
			"fieldname": "fulfillment_pct",
			"label": _("% Fulfillment"),
			"fieldtype": "Percent",
			"width": 120
		}
	]

def get_data(filters):
	"""Fetch and process report data"""
	
	conditions = get_conditions(filters)
	
	query = """
		SELECT 
			soi.parent as so_no,
			soi.item_code,
			soi.item_name,
			soi.qty as qty_in_so,
			SUM(dni.qty), 0 as qty_in_dn
		FROM 
			`tabSales Order Item` soi
		JOIN 
			`tabSales Order` so ON so.name = soi.parent
		LEFT JOIN 
			`tabDelivery Note Item` dni ON dni.so_detail = soi.name 
			AND dni.docstatus = 1
		WHERE 
			so.docstatus = 1
			{conditions}
		GROUP BY 
			soi.name, soi.parent, soi.item_code, soi.item_name, soi.qty
		ORDER BY 
			soi.parent, soi.idx
	""".format(conditions=conditions)
	
	data = frappe.db.sql(query, filters, as_dict=1)
	
	# Calculate outstanding and fulfillment percentage
	for row in data:
		row['outstanding'] = row['qty_in_so'] - row['qty_in_dn']
		
		if row['qty_in_so'] > 0:
			row['fulfillment_pct'] = ((row['qty_in_dn'] / row['qty_in_so']) * 100)
		else:
			row['fulfillment_pct'] = 0
	
	return data

def get_conditions(filters):
	conditions = []
	
	if filters.get("from_date"):
		conditions.append("so.transaction_date >= %(from_date)s")
	
	if filters.get("company"):
		conditions.append("so.transaction_date >= %(company)s")
	
	if filters.get("to_date"):
		conditions.append("so.transaction_date <= %(to_date)s")
	
	if filters.get("sales_order"):
		conditions.append("so.name = %(sales_order)s")
	
	if filters.get("customer"):
		conditions.append("so.customer = %(customer)s")
	
	if filters.get("item_code"):
		conditions.append("soi.item_code = %(item_code)s")
	
	return " AND " + " AND ".join(conditions) if conditions else ""