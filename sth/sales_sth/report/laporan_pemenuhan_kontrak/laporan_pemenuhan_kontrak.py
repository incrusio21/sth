import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
  return [
		{
			"fieldname": "kode_pt",
			"label": _("Kode PT"),
			"fieldtype": "Data",
			"width": 200
		},
		{
			"fieldname": "no_kontrak",
			"label": _("No Kontrak"),
			"fieldtype": "Data",
			"width": 250
		},
		{
			"fieldname": "komoditi",
			"label": _("Komoditi"),
			"fieldtype": "Data",
			"width": 250
		},
		{
			"fieldname": "tanggal_kontrak",
			"label": _("Tanggal Kontrak"),
			"fieldtype": "Date",
			"width": 250
		},
		{
			"fieldname": "pembeli",
			"label": _("Pembeli"),
			"fieldtype": "Data",
			"width": 300
		},
		{
			"fieldname": "estimasi_pengiriman",
			"label": _("Estimasi Pengiriman"),
			"fieldtype": "Data",
			"width": 250
		},
		{
			"fieldname": "banyaknya",
			"label": _("Banyaknya"),
			"fieldtype": "Float",
			"width": 120
		},
		{
			"fieldname": "pemenuhan",
			"label": _("Pemenuhan"),
			"fieldtype": "Float",
			"width": 120
		},
		{
			"fieldname": "berat_bersih_pembeli",
			"label": _("Berat Bersih Pembeli"),
			"fieldtype": "Float",
			"width": 120
		},
		{
			"fieldname": "sisa",
			"label": _("Sisa"),
			"fieldtype": "Float",
			"width": 120
		},
		{
			"fieldname": "mata_uang",
			"label": _("Mata Uang"),
			"fieldtype": "Data",
			"width": 120
		},
	]

def get_data(filters):
  data = []
  conditions = get_condition(filters)
  
  query = frappe.db.sql("""
		SELECT 
		c.abbr as kode_pt,
		so.name as no_kontrak_alias,
		CASE
			WHEN so.no_kontrak_external IS NOT NULL THEN so.no_kontrak_external
			ELSE so.name
		END as no_kontrak,
		so.komoditi as komoditi,
		so.transaction_date as tanggal_kontrak,
		so.company as pembeli,
		CONCAT(so.delivery_date, ' s.d ', so.end_delivery_date) as estimasi_pengiriman,
		soi.qty as banyaknya,
		SUM(t.netto_2) as pemenuhan,
		SUM(sii.qty_timbang_customer) as berat_bersih_pembeli,
		(soi.qty - SUM(t.netto_2)) as sisa,
		'IDR' as mata_uang
		FROM `tabSales Order` as so
		JOIN `tabCompany` as c ON c.name = so.company
		LEFT JOIN `tabSales Order Item` as soi ON soi.parent = so.name
		LEFT JOIN `tabDelivery Order` as do ON do.sales_order = so.name
		LEFT JOIN `tabTimbangan` as t ON t.do_no = do.name
		LEFT JOIN `tabSales Invoice Item` as sii ON sii.delivery_note = t.delivery_note
		WHERE so.docstatus = 1 {}
  	GROUP BY so.name;
	""".format(conditions), filters, as_dict=True)

  for row in query:
    data.append(row)
  
  return data

def get_condition(filters):
	conditions = ""

	if filters.get("company"):
		conditions += " AND so.pt = %(company)s"

	if filters.get("unit"):
		conditions += " AND so.unit = %(unit)s"

	if filters.get("komoditi"):
		conditions += " AND so.komoditi = %(komoditi)s"

	if filters.get("from_date") and filters.get("to_date"):
		conditions += " AND so.transaction_date BETWEEN %(from_date)s AND %(to_date)s"

	return conditions

# def get_columns():
# 	return [
# 		{
# 			"fieldname": "so_no",
# 			"label": _("SO No"),
# 			"fieldtype": "Link",
# 			"options": "Sales Order",
# 			"width": 200
# 		},
# 		{
# 			"fieldname": "item_code",
# 			"label": _("Item Code"),
# 			"fieldtype": "Link",
# 			"options": "Item",
# 			"width": 250
# 		},
# 		{
# 			"fieldname": "item_name",
# 			"label": _("Item Name"),
# 			"fieldtype": "Data",
# 			"width": 200
# 		},
# 		{
# 			"fieldname": "qty_in_so",
# 			"label": _("Qty in SO"),
# 			"fieldtype": "Float",
# 			"width": 120
# 		},
# 		{
# 			"fieldname": "qty_in_dn",
# 			"label": _("Qty in DN"),
# 			"fieldtype": "Float",
# 			"width": 120
# 		},
# 		{
# 			"fieldname": "outstanding",
# 			"label": _("Outstanding"),
# 			"fieldtype": "Float",
# 			"width": 120
# 		},
# 		{
# 			"fieldname": "fulfillment_pct",
# 			"label": _("% Fulfillment"),
# 			"fieldtype": "Percent",
# 			"width": 120
# 		}
# 	]

# def get_data(filters):
# 	"""Fetch and process report data"""
	
# 	conditions = get_conditions(filters)
	
# 	query = """
# 		SELECT 
# 			soi.parent as so_no,
# 			soi.item_code,
# 			soi.item_name,
# 			soi.qty as qty_in_so,
# 			SUM(dni.qty), 0 as qty_in_dn
# 		FROM 
# 			`tabSales Order Item` soi
# 		JOIN 
# 			`tabSales Order` so ON so.name = soi.parent
# 		LEFT JOIN 
# 			`tabDelivery Note Item` dni ON dni.so_detail = soi.name 
# 			AND dni.docstatus = 1
# 		WHERE 
# 			so.docstatus = 1
# 			{conditions}
# 		GROUP BY 
# 			soi.name, soi.parent, soi.item_code, soi.item_name, soi.qty
# 		ORDER BY 
# 			soi.parent, soi.idx
# 	""".format(conditions=conditions)
	
# 	data = frappe.db.sql(query, filters, as_dict=1)
	
# 	# Calculate outstanding and fulfillment percentage
# 	for row in data:
# 		row['outstanding'] = row['qty_in_so'] - row['qty_in_dn']
		
# 		if row['qty_in_so'] > 0:
# 			row['fulfillment_pct'] = ((row['qty_in_dn'] / row['qty_in_so']) * 100)
# 		else:
# 			row['fulfillment_pct'] = 0
	
# 	return data

# def get_conditions(filters):
# 	conditions = []
	
# 	if filters.get("from_date"):
# 		conditions.append("so.transaction_date >= %(from_date)s")
	
# 	if filters.get("company"):
# 		conditions.append("so.transaction_date >= %(company)s")
	
# 	if filters.get("to_date"):
# 		conditions.append("so.transaction_date <= %(to_date)s")
	
# 	if filters.get("sales_order"):
# 		conditions.append("so.name = %(sales_order)s")
	
# 	if filters.get("customer"):
# 		conditions.append("so.customer = %(customer)s")
	
# 	if filters.get("item_code"):
# 		conditions.append("soi.item_code = %(item_code)s")
	
# 	return " AND " + " AND ".join(conditions) if conditions else ""