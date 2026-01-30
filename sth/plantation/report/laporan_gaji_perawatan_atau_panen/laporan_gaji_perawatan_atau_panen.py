import frappe
from frappe import _
from frappe.utils import getdate

def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data

def get_columns(filters):
	columns = [
		{
			"label": _("No Transaksi"),
			"fieldname": "voucher_no",
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 160,
			"align": "left"
		},
		{
			"label": _("Blok"),
			"fieldname": "blok",
			"fieldtype": "Data",
			"width": 120,
			"align": "left"
		},
		{
			"label": _("NIK"),
			"fieldname": "nik",
			"fieldtype": "Data",
			"width": 120,
			"align": "left"
		},
		{
			"label": _("ID Karyawan"),
			"fieldname": "employee",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 150,
			"align": "left"
		},
		{
			"label": _("Nama Karyawan"),
			"fieldname": "employee_name",
			"fieldtype": "Data",			
			"width": 280,
			"align": "left"
		},
		{
			"label": _("Nomor Rekening"),
			"fieldname": "norek_karyawan",
			"fieldtype": "Data",			
			"width": 150,
			"align": "left"
		},
		{
			"label": _("Tanggal"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 120,
			"align": "left"
		},
		{
			"label": _("Kegiatan"),
			"fieldname": "kegiatan",
			"fieldtype": "Data",
			"width": 350,
			"align": "left"
		},
		{
			"label": _("Hasil Kerja"),
			"fieldname": "hasil_kerja_qty",
			"fieldtype": "Float",
			"width": 100,
			"align": "right"
		},
		{
			"label": _("Brondolan (KG)"),
			"fieldname": "brondolan",
			"fieldtype": "Float",
			"width": 150,
			"align": "right"
		},
		{
			"label": _("Total Tonase"),
			"fieldname": "total_tonase",
			"fieldtype": "Float",
			"width": 150,
			"align": "right"
		},
		{
			"label": _("Satuan"),
			"fieldname": "satuan",
			"fieldtype": "Data",
			"width": 80,
			"align": "left"
		},
		{
			"label": _("Basis"),
			"fieldname": "basis",
			"fieldtype": "Float",
			"width": 80,
			"align": "right"
		},
		{
			"label": _("Rupiah/Satuan"),
			"fieldname": "rupiah_satuan",
			"fieldtype": "Currency",
			"width": 150,
			"align": "right"
		},
		{
			"label": _("Rp Premi"),
			"fieldname": "rp_premi",
			"fieldtype": "Currency",
			"width": 120,
			"align": "right"
		},
		{
			"label": _("Kondisi"),
			"fieldname": "kondisi",
			"fieldtype": "Data",
			"width": 100,
			"align": "left"
		},
		{
			"label": _("Tipe"),
			"fieldname": "tipe",
			"fieldtype": "Data",
			"width": 80,
			"align": "left"
		},
		{
			"label": _("P.Upah"),
			"fieldname": "p_upah",
			"fieldtype": "Currency",
			"width": 120,
			"align": "right"
		},
		{
			"label": _("P.Premi"),
			"fieldname": "p_premi",
			"fieldtype": "Currency",
			"width": 120,
			"align": "right"
		},
		{
			"label": _("Total"),
			"fieldname": "total",
			"fieldtype": "Currency",
			"width": 120,
			"align": "right"
		},
		{
			"label": _("Voucher Type"),
			"fieldname": "voucher_type",
			"fieldtype": "Link",
			"options":"DocType",
			"width": 120,
			"hidden": 1
		}
	]
	return columns

def get_data(filters):
	conditions = get_conditions(filters)
	
	query = """
		SELECT 
			epl.voucher_no,
			epl.voucher_type,
			epl.voucher_detail_no,
			epl.employee,
			epl.posting_date,
			epl.component_type,
			epl.amount
		FROM 
			`tabEmployee Payment Log` epl
		WHERE 
			epl.status = "Approved"
			AND epl.voucher_type IN ('Buku Kerja Mandor Perawatan', 'Buku Kerja Mandor Panen')
			{conditions}
		ORDER BY 
			epl.employee,epl.voucher_type DESC, epl.posting_date, epl.voucher_no
	""".format(conditions=conditions,debug=1)
	
	epl_data = frappe.db.sql(query, filters, as_dict=1)
	
	voucher_dict = {}
	for row in epl_data:
		key = (row.employee, row.voucher_no)
		if key not in voucher_dict:
			voucher_dict[key] = {
				'voucher_no': row.voucher_no,
				'voucher_type': row.voucher_type,
				'employee': row.employee,
				'posting_date': row.posting_date,
				'p_upah': 0,
				'p_premi': 0
			}
		
		if row.component_type == 'Upah':
			voucher_dict[key]['p_upah'] = row.amount
		elif row.component_type == 'Premi':
			voucher_dict[key]['p_premi'] = row.amount

		if row.voucher_type == 'Buku Kerja Mandor Perawatan':
			voucher_detail_doc = frappe.get_doc("Detail BKM Hasil Kerja Perawatan", row.voucher_detail_no)
			voucher_dict[key]['total_tonase'] = voucher_detail_doc.get('qty', 0)
		elif row.voucher_type == 'Buku Kerja Mandor Panen':
			voucher_detail_doc = frappe.get_doc("Detail BKM Hasil Kerja Panen", row.voucher_detail_no)
			voucher_dict[key]['total_tonase'] = voucher_detail_doc.get('qty', 0)
	
	data = []
	employee_totals = {}
	
	for key, voucher_data in voucher_dict.items():
		employee, voucher_no = key
		
		if not voucher_data.get('voucher_type') or not voucher_no:
			continue
			
		voucher_doc = frappe.get_doc(voucher_data.get('voucher_type'), voucher_no)
		
		if not voucher_data.get('employee'):
			continue
			
		employee_doc = frappe.get_doc("Employee", voucher_data['employee'])
		
		kegiatan_doc = None
		if voucher_doc.get('kegiatan'):
			try:
				kegiatan_doc = frappe.get_doc("Kegiatan", voucher_doc.kegiatan)
			except:
				kegiatan_doc = None
		
		row = {
			'voucher_no': voucher_no,
			'blok': voucher_doc.get('blok', ''),
			'nik': employee_doc.get('no_ktp', ''),
			'employee': voucher_data['employee'],
			'norek_karyawan': employee_doc.get('bank_ac_no', ''),
			'employee_name': employee_doc.get('employee_name', ''),
			'posting_date': voucher_data['posting_date'],
			'kegiatan': voucher_doc.get('kegiatan_account', ''),
			'hasil_kerja_qty': voucher_doc.get('hasil_kerja_qty', 0) if voucher_data['voucher_type'] == 'Buku Kerja Mandor Perawatan' else voucher_doc.get('weight_total', 0) ,
			'brondolan': voucher_doc.get('hasil_kerja_qty_brondolan', 0) if voucher_data['voucher_type'] == 'Buku Kerja Mandor Panen' else 0,
			'total_tonase': voucher_data['total_tonase'],
			'satuan': kegiatan_doc.get('uom', '') if kegiatan_doc else '',
			'basis': voucher_doc.get('volume_basis', 0),
			'rupiah_satuan': voucher_doc.get('rupiah_basis', 0),
			'rp_premi': voucher_doc.get('rupiah_premi', 0) if voucher_data['voucher_type'] == 'Buku Kerja Mandor Perawatan' else 0,
			'kondisi': voucher_doc.get('status_panen', '') if voucher_data['voucher_type'] == 'Buku Kerja Mandor Panen' else '',
			'tipe': 'Manual' if voucher_data['voucher_type'] == 'Buku Kerja Mandor Panen' and voucher_doc.get('manual_hk') == 1 else '',
			'p_upah': voucher_data['p_upah'],
			'p_premi': voucher_data['p_premi'],
			'total': voucher_data['p_upah'] + voucher_data['p_premi'],
			'voucher_type':voucher_data.get('voucher_type')
		}
		
		data.append(row)
		
		employee = voucher_data['employee']
		if employee not in employee_totals:
			employee_totals[employee] = {
				'total_tonase': 0,
				'p_upah': 0,
				'p_premi': 0,
				'total': 0
			}
		
		employee_totals[employee]['total_tonase'] += row['total_tonase']
		employee_totals[employee]['p_upah'] += row['p_upah']
		employee_totals[employee]['p_premi'] += row['p_premi']
		employee_totals[employee]['total'] += row['total']
		
	
	final_data = []
	current_employee = None
	current_employee_name = ""
	
	for row in data:
		if current_employee != row['employee']:
			if current_employee:
				final_data.append({
					'voucher_no': '',
					'blok': '',
					'nik': '',
					'employee_name': f"<b>Total {current_employee_name}</b>",
					'posting_date': '',
					'kegiatan': '',
					'hasil_kerja_qty': None,
					'brondolan': None,
					'satuan': '',
					'basis': None,
					'rupiah_satuan': None,
					'rp_premi': None,
					'kondisi': '',
					'tipe': '',
					'total_tonase': employee_totals[current_employee]['total_tonase'],
					'p_upah': employee_totals[current_employee]['p_upah'],
					'p_premi': employee_totals[current_employee]['p_premi'], 
					'total': employee_totals[current_employee]['total'], 
				})
			current_employee = row['employee']
			current_employee_name = frappe.get_doc("Employee", row['employee']).get('employee_name', '')
		
		final_data.append(row)
	
	if current_employee:
		final_data.append({
			'voucher_no': '',
			'blok': '',
			'nik': '',
			'employee_name': f"<b>Total {current_employee_name}</b>",
			'posting_date': '',
			'kegiatan': '',
			'hasil_kerja_qty': None,
			'brondolan': None,
			'satuan': '',
			'basis': None,
			'rupiah_satuan': None,
			'rp_premi': None,
			'kondisi': '',
			'tipe': '',
			'total_tonase': employee_totals[current_employee]['total_tonase'],
			'p_upah': employee_totals[current_employee]['p_upah'],
			'p_premi': employee_totals[current_employee]['p_premi'], 
			'total': employee_totals[current_employee]['total'], 
		})
	
	return final_data

def get_conditions(filters):
	conditions = []
	
	if filters.get("bulan"):
		bulan_map = {
			"Januari": 1, "Februari": 2, "Maret": 3, "April": 4,
			"Mei": 5, "Juni": 6, "Juli": 7, "Agustus": 8,
			"September": 9, "Oktober": 10, "November": 11, "Desember": 12
		}
		month_num = bulan_map.get(filters.get("bulan"))
		if month_num:
			conditions.append(f"MONTH(epl.posting_date) = {month_num}")
	
	if filters.get("tahun"):
		conditions.append("YEAR(epl.posting_date) = %(tahun)s")
	
	if filters.get("employee"):
		conditions.append("epl.employee = %(employee)s")
	
	return " AND " + " AND ".join(conditions) if conditions else ""