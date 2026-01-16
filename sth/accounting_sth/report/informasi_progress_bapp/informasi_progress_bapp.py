import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	return [
		{
			"fieldname": "bapp_no",
			"label": _("No BAPP"),
			"fieldtype": "Link",
			"options": "BAPP",
			"width": 150
		},
		{
			"fieldname": "unit",
			"label": _("Unit"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "supplier",
			"label": _("Supplier"),
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 150
		},
		{
			"fieldname": "nama_kegiatan",
			"label": _("Nama Kegiatan"),
			"fieldtype": "Data",
			"width": 200
		},
		{
			"fieldname": "progress_kegiatan",
			"label": _("Progress Kegiatan"),
			"fieldtype": "Percent",
			"width": 120
		},
		{
			"fieldname": "pinv_no",
			"label": _("PINV No"),
			"fieldtype": "Data",
			"width": 200
		}
	]

def get_data(filters):
	data = []
	
	# Query untuk ambil semua BAPP dengan items
	bapp_list = frappe.db.sql("""
		SELECT 
			b.name as bapp_no,
			b.unit,
			b.supplier,
			bi.name as bapp_item_name,
			bi.kegiatan_name,
			bi.qty as bapp_qty
		FROM 
			`tabBAPP` b
		LEFT JOIN 
			`tabBAPP Item` bi ON bi.parent = b.name
		WHERE
			b.docstatus = 1
			{conditions}
		ORDER BY 
			b.name, bi.idx
	""".format(conditions=get_conditions(filters)), filters, as_dict=1)
	
	for bapp in bapp_list:
		# Hitung total qty dari PINV items yang refer ke bapp_item ini
		pinv_data = frappe.db.sql("""
			SELECT 
				pi.parent as pinv_no,
				SUM(pi.qty) as total_qty
			FROM 
				`tabPurchase Invoice Item` pi
			INNER JOIN
				`tabPurchase Invoice` p ON p.name = pi.parent
			WHERE 
				pi.bapp_detail = %s
				AND p.docstatus = 1
			GROUP BY 
				pi.parent
		""", (bapp.bapp_item_name), as_dict=1)
		
		# Hitung total qty dari semua PINV untuk item ini
		total_pinv_qty = sum([d.total_qty for d in pinv_data]) if pinv_data else 0
		
		# Hitung progress percentage
		progress = (total_pinv_qty / bapp.bapp_qty * 100) if bapp.bapp_qty else 0
		
		# Ambil semua PINV No yang terkait
		pinv_numbers = ", ".join([d.pinv_no for d in pinv_data]) if pinv_data else "-"
		
		data.append({
			"bapp_no": bapp.bapp_no,
			"unit": bapp.unit,
			"supplier": bapp.supplier,
			"nama_kegiatan": bapp.kegiatan_name,
			"progress_kegiatan": progress,
			"pinv_no": pinv_numbers
		})
	
	return data

def get_conditions(filters):
	conditions = []
	
	if filters.get("bapp_no"):
		conditions.append("b.name = %(bapp_no)s")
	
	if filters.get("supplier"):
		conditions.append("b.supplier = %(supplier)s")
	
	if filters.get("unit"):
		conditions.append("b.unit = %(unit)s")
	
	if filters.get("from_date"):
		conditions.append("b.creation >= %(from_date)s")
	
	if filters.get("to_date"):
		conditions.append("b.creation <= %(to_date)s")
	
	return " AND " + " AND ".join(conditions) if conditions else ""