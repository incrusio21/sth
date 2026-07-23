# import frappe
# from frappe import _
# from frappe.utils import getdate
# import json

# def execute(filters=None):
# 	columns = get_columns(filters)
# 	data = get_data(filters)
# 	return columns, data

# def get_columns(filters):
# 	columns = [
# 		{
# 			"label": _("No Transaksi"),
# 			"fieldname": "voucher_no",
# 			"fieldtype": "Dynamic Link",
# 			"options": "voucher_type",
# 			"width": 160,
# 			"align": "left"
# 		},
# 		{
# 			"label": _("Blok"),
# 			"fieldname": "blok",
# 			"fieldtype": "Data",
# 			"width": 120,
# 			"align": "left"
# 		},
# 		{
# 			"label": _("NIK"),
# 			"fieldname": "nik",
# 			"fieldtype": "Data",
# 			"width": 120,
# 			"align": "left"
# 		},
# 		{
# 			"label": _("ID Karyawan"),
# 			"fieldname": "employee",
# 			"fieldtype": "Link",
# 			"options": "Employee",
# 			"width": 150,
# 			"align": "left"
# 		},
# 		{
# 			"label": _("Nama Karyawan"),
# 			"fieldname": "employee_name",
# 			"fieldtype": "Data",			
# 			"width": 280,
# 			"align": "left"
# 		},
# 		{
# 			"label": _("Nomor Rekening"),
# 			"fieldname": "norek_karyawan",
# 			"fieldtype": "Data",			
# 			"width": 150,
# 			"align": "left"
# 		},
# 		{
# 			"label": _("Tanggal"),
# 			"fieldname": "posting_date",
# 			"fieldtype": "Date",
# 			"width": 120,
# 			"align": "left"
# 		},
# 		{
# 			"label": _("Kegiatan"),
# 			"fieldname": "kegiatan",
# 			"fieldtype": "Data",
# 			"width": 350,
# 			"align": "left"
# 		},
# 		{
# 			"label": _("Hasil Kerja"),
# 			"fieldname": "hasil_kerja_qty",
# 			"fieldtype": "Float",
# 			"width": 100,
# 			"align": "right"
# 		},
# 		{
# 			"label": _("Brondolan (KG)"),
# 			"fieldname": "brondolan",
# 			"fieldtype": "Float",
# 			"width": 150,
# 			"align": "right"
# 		},
# 		{
# 			"label": _("Total Tonase"),
# 			"fieldname": "total_tonase",
# 			"fieldtype": "Float",
# 			"width": 150,
# 			"align": "right"
# 		},
# 		{
# 			"label": _("Satuan"),
# 			"fieldname": "satuan",
# 			"fieldtype": "Data",
# 			"width": 80,
# 			"align": "left"
# 		},
# 		{
# 			"label": _("Basis"),
# 			"fieldname": "basis",
# 			"fieldtype": "Float",
# 			"width": 80,
# 			"align": "right"
# 		},
# 		{
# 			"label": _("Rupiah/Satuan"),
# 			"fieldname": "rupiah_satuan",
# 			"fieldtype": "Currency",
# 			"width": 150,
# 			"align": "right"
# 		},
# 		{
# 			"label": _("Rp Premi"),
# 			"fieldname": "rp_premi",
# 			"fieldtype": "Currency",
# 			"width": 120,
# 			"align": "right"
# 		},
# 		{
# 			"label": _("Kondisi"),
# 			"fieldname": "kondisi",
# 			"fieldtype": "Data",
# 			"width": 100,
# 			"align": "left"
# 		},
# 		{
# 			"label": _("Tipe"),
# 			"fieldname": "tipe",
# 			"fieldtype": "Data",
# 			"width": 80,
# 			"align": "left"
# 		},
# 		{
# 			"label": _("P.Upah"),
# 			"fieldname": "p_upah",
# 			"fieldtype": "Currency",
# 			"width": 120,
# 			"align": "right"
# 		},
# 		{
# 			"label": _("P.Premi"),
# 			"fieldname": "p_premi",
# 			"fieldtype": "Currency",
# 			"width": 120,
# 			"align": "right"
# 		},
# 		{
# 			"label": _("Total"),
# 			"fieldname": "total",
# 			"fieldtype": "Currency",
# 			"width": 120,
# 			"align": "right"
# 		},
# 		{
# 			"label": _("Voucher Type"),
# 			"fieldname": "voucher_type",
# 			"fieldtype": "Link",
# 			"options":"DocType",
# 			"width": 120,
# 			"hidden": 1
# 		}
# 	]
# 	return columns

# def get_data(filters):
# 	conditions = get_conditions(filters)
	
# 	# query = """
# 	# 	SELECT 
# 	# 		epl.voucher_no,
# 	# 		epl.voucher_type,
# 	# 		epl.voucher_detail_no,
# 	# 		epl.employee,
# 	# 		epl.posting_date,
# 	# 		epl.component_type,
# 	# 		epl.amount
# 	# 	FROM 
# 	# 		`tabEmployee Payment Log` epl
# 	# 	WHERE 
# 	# 		epl.status = "Approved"
# 	# 		AND epl.voucher_type IN ('Buku Kerja Mandor Perawatan', 'Buku Kerja Mandor Panen')
# 	# 		{conditions}
# 	# 	ORDER BY 
# 	# 		epl.employee,epl.voucher_type DESC, epl.posting_date, epl.voucher_no
# 	# """.format(conditions=conditions,debug=1)
# 	query = """
# 		SELECT 
# 			epl.voucher_no,
# 			epl.voucher_type,
# 			epl.voucher_detail_no,
# 			epl.employee,
# 			epl.posting_date,
# 			epl.component_type,
# 			epl.amount
# 		FROM 
# 			`tabEmployee Payment Log` epl
# 		WHERE 
# 			epl.status = "Approved"
# 			AND epl.voucher_type IN ('Buku Kerja Mandor Perawatan')
# 			{conditions}
# 		ORDER BY 
# 			epl.employee,epl.voucher_type DESC, epl.posting_date, epl.voucher_no
# 	""".format(conditions=conditions,debug=1)
	
# 	epl_data = frappe.db.sql(query, filters, as_dict=1)

# 	voucher_dict = {}
# 	for row in epl_data:
# 		# key = row.voucher_no
# 		key = f"{row.voucher_no}-{row.employee}"
# 		if key not in voucher_dict:
# 			voucher_dict[key] = {
# 				'voucher_no': row.voucher_no,
# 				'voucher_type': row.voucher_type,
# 				'employee': row.employee,
# 				'posting_date': row.posting_date,
# 				'p_upah': 0,
# 				'p_premi': 0
# 			}
		
# 		if row.component_type == 'Upah':
# 			voucher_dict[key]['p_upah'] = row.amount
# 		elif row.component_type == 'Premi':
# 			voucher_dict[key]['p_premi'] = row.amount

# 		if row.voucher_type == 'Buku Kerja Mandor Perawatan':
# 			# voucher_detail_doc = frappe.get_doc("Detail BKM Hasil Kerja Perawatan", row.voucher_detail_no)
# 			voucher_dict[key]['total_tonase'] = 0
# 		elif row.voucher_type == 'Buku Kerja Mandor Panen':
# 			voucher_detail_doc = frappe.get_doc("Detail BKM Hasil Kerja Panen", row.voucher_detail_no)
# 			voucher_dict[key]['total_tonase'] = voucher_detail_doc.get('qty', 0)
	
# 	data = []
# 	employee_totals = {}
	
# 	for voucher_no, voucher_data in voucher_dict.items():
		
# 		if not voucher_data.get('voucher_type') or not voucher_data.get('voucher_no'):
# 			continue
			
# 		voucher_doc = frappe.get_doc(voucher_data.get('voucher_type'), voucher_data.get('voucher_no'))
		
# 		if not voucher_data.get('employee'):
# 			continue
			
# 		employee_doc = frappe.get_doc("Employee", voucher_data['employee'])
		
# 		kegiatan_doc = None
# 		if voucher_doc.get('kegiatan'):
# 			try:
# 				kegiatan_doc = frappe.get_doc("Kegiatan", voucher_doc.kegiatan)
# 			except:
# 				kegiatan_doc = None
		
# 		row = {
# 			'voucher_no': voucher_data.get('voucher_no'),
# 			'blok': voucher_doc.get('blok', ''),
# 			'nik': employee_doc.get('no_ktp', ''),
# 			'employee': voucher_data['employee'],
# 			'norek_karyawan': employee_doc.get('bank_ac_no', ''),
# 			'employee_name': employee_doc.get('employee_name', ''),
# 			'posting_date': voucher_data['posting_date'],
# 			'kegiatan': voucher_doc.get('kegiatan_account', ''),
# 			'hasil_kerja_qty': voucher_doc.get('hasil_kerja_qty', 0) if voucher_data['voucher_type'] == 'Buku Kerja Mandor Perawatan' else voucher_doc.get('weight_total', 0) ,
# 			'brondolan': voucher_doc.get('hasil_kerja_qty_brondolan', 0) if voucher_data['voucher_type'] == 'Buku Kerja Mandor Panen' else 0,
# 			'total_tonase': voucher_data['total_tonase'],
# 			'satuan': kegiatan_doc.get('uom', '') if kegiatan_doc else '',
# 			'basis': voucher_doc.get('volume_basis', 0),
# 			'rupiah_satuan': voucher_doc.get('rupiah_basis', 0),
# 			'rp_premi': voucher_doc.get('rupiah_premi', 0) if voucher_data['voucher_type'] == 'Buku Kerja Mandor Perawatan' else 0,
# 			'kondisi': voucher_doc.get('status_panen', '') if voucher_data['voucher_type'] == 'Buku Kerja Mandor Panen' else '',
# 			'tipe': 'Manual' if voucher_data['voucher_type'] == 'Buku Kerja Mandor Panen' and voucher_doc.get('manual_hk') == 1 else '',
# 			'p_upah': voucher_data['p_upah'],
# 			'p_premi': voucher_data['p_premi'],
# 			'total': voucher_data['p_upah'] + voucher_data['p_premi'],
# 			'voucher_type':voucher_data.get('voucher_type')
# 		}
		
# 		data.append(row)
		
# 		employee = voucher_data['employee']
# 		if employee not in employee_totals:
# 			employee_totals[employee] = {
# 				'total_tonase': 0,
# 				'p_upah': 0,
# 				'p_premi': 0,
# 				'total': 0
# 			}
		
# 		employee_totals[employee]['voucher_type'] = row['voucher_type']
# 		employee_totals[employee]['total_tonase'] += row['total_tonase']
# 		employee_totals[employee]['satuan'] = row['satuan']
# 		employee_totals[employee]['p_upah'] += row['p_upah']
# 		employee_totals[employee]['p_premi'] += row['p_premi']
# 		employee_totals[employee]['total'] += row['total']
		
	
# 	final_data = []
# 	current_employee = None
# 	current_employee_name = ""
	
# 	for row in sorted(data, key=lambda x: x['employee']):
# 		if current_employee != row['employee']:
# 			if current_employee:
# 				final_data.append({
# 					'voucher_no': '',
# 					'blok': '',
# 					'nik': '',
# 					'employee_name': f"<b>Total {current_employee_name}</b>",
# 					'posting_date': '',
# 					'kegiatan': '',
# 					'hasil_kerja_qty': None,
# 					'brondolan': None,
# 					'satuan': '' if employee_totals[current_employee]['voucher_type'] == "Buku Kerja Mandor Perawatan" else employee_totals[current_employee]['satuan'],
# 					'basis': None,
# 					'rupiah_satuan': None,
# 					'rp_premi': None,
# 					'kondisi': '',
# 					'tipe': '',
# 					'total_tonase': None if employee_totals[current_employee]['voucher_type'] == "Buku Kerja Mandor Perawatan" else employee_totals[current_employee]['total_tonase'],
# 					'p_upah': employee_totals[current_employee]['p_upah'],
# 					'p_premi': employee_totals[current_employee]['p_premi'], 
# 					'total': employee_totals[current_employee]['total'], 
# 				})
# 			current_employee = row['employee']
# 			current_employee_name = frappe.get_doc("Employee", row['employee']).get('employee_name', '')
		
# 		final_data.append(row)
	
# 	if current_employee:
# 		final_data.append({
# 			'voucher_no': '',
# 			'blok': '',
# 			'nik': '',
# 			'employee_name': f"<b>Total {current_employee_name}</b>",
# 			'posting_date': '',
# 			'kegiatan': '',
# 			'hasil_kerja_qty': None,
# 			'brondolan': None,
# 			'satuan': '' if employee_totals[current_employee]['voucher_type'] == "Buku Kerja Mandor Perawatan" else employee_totals[current_employee]['satuan'],
# 			'basis': None,
# 			'rupiah_satuan': None,
# 			'rp_premi': None,
# 			'kondisi': '',
# 			'tipe': '',
# 			'total_tonase': None if employee_totals[current_employee]['voucher_type'] == "Buku Kerja Mandor Perawatan" else employee_totals[current_employee]['total_tonase'],
# 			'p_upah': employee_totals[current_employee]['p_upah'],
# 			'p_premi': employee_totals[current_employee]['p_premi'], 
# 			'total': employee_totals[current_employee]['total'], 
# 		})
	
# 	return final_data

# def get_conditions(filters):
# 	conditions = []
	
# 	if filters.get("bulan"):
# 		bulan_map = {
# 			"Januari": 1, "Februari": 2, "Maret": 3, "April": 4,
# 			"Mei": 5, "Juni": 6, "Juli": 7, "Agustus": 8,
# 			"September": 9, "Oktober": 10, "November": 11, "Desember": 12
# 		}
# 		month_num = bulan_map.get(filters.get("bulan"))
# 		if month_num:
# 			conditions.append(f"MONTH(epl.posting_date) = {month_num}")
	
# 	if filters.get("tahun"):
# 		conditions.append("YEAR(epl.posting_date) = %(tahun)s")
	
# 	if filters.get("employee"):
# 		conditions.append("epl.employee = %(employee)s")

# 	if filters.get("bkm") and filters.get("bkm") != "All":
# 		bkm_map = {
# 			"Panen": "Buku Kerja Mandor Panen",
# 			"Perawatan": "Buku Kerja Mandor Perawatan"
# 		}
# 		voucher_type = bkm_map.get(filters.get("bkm"))
# 		if voucher_type:
# 			conditions.append("epl.voucher_type = %(voucher_type_filter)s")
# 			filters["voucher_type_filter"] = voucher_type
	
# 	return " AND " + " AND ".join(conditions) if conditions else ""

import frappe
from frappe import _
from frappe.utils import getdate
import json

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
	bkm_filter = filters.get("bkm") or "All"

	data = []
	employee_totals = {}

	if bkm_filter in ("All", "Perawatan"):
		data += get_perawatan_data(filters)

	if bkm_filter in ("All", "Panen"):
		data += get_panen_data(filters)

	for row in data:
		employee = row['employee']
		if employee not in employee_totals:
			employee_totals[employee] = {
				'total_tonase': 0,
				'p_upah': 0,
				'p_premi': 0,
				'total': 0
			}

		employee_totals[employee]['voucher_type'] = row['voucher_type']
		employee_totals[employee]['total_tonase'] += row['total_tonase']
		employee_totals[employee]['satuan'] = row['satuan']
		employee_totals[employee]['p_upah'] += row['p_upah']
		employee_totals[employee]['p_premi'] += row['p_premi']
		employee_totals[employee]['total'] += row['total']

	final_data = []
	current_employee = None
	current_employee_name = ""

	def build_subtotal_row(employee):
		return {
			'voucher_no': '',
			'blok': '',
			'nik': '',
			'employee_name': f"<b>Total {current_employee_name}</b>",
			'posting_date': '',
			'kegiatan': '',
			'hasil_kerja_qty': None,
			'brondolan': None,
			'satuan': '' if employee_totals[employee]['voucher_type'] == "Buku Kerja Mandor Perawatan" else employee_totals[employee]['satuan'],
			'basis': None,
			'rupiah_satuan': None,
			'rp_premi': None,
			'kondisi': '',
			'tipe': '',
			'total_tonase': None if employee_totals[employee]['voucher_type'] == "Buku Kerja Mandor Perawatan" else employee_totals[employee]['total_tonase'],
			'p_upah': employee_totals[employee]['p_upah'],
			'p_premi': employee_totals[employee]['p_premi'],
			'total': employee_totals[employee]['total'],
		}

	for row in sorted(data, key=lambda x: x['employee']):
		if current_employee != row['employee']:
			if current_employee:
				final_data.append(build_subtotal_row(current_employee))
			current_employee = row['employee']
			current_employee_name = row['employee_name']

		final_data.append(row)

	if current_employee:
		final_data.append(build_subtotal_row(current_employee))

	return final_data

def get_perawatan_data(filters):
	conditions = get_conditions_epl(filters)

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
			AND epl.voucher_type IN ('Buku Kerja Mandor Perawatan')
			{conditions}
		ORDER BY 
			epl.employee, epl.posting_date, epl.voucher_no
	""".format(conditions=conditions)

	epl_data = frappe.db.sql(query, filters, as_dict=1)

	voucher_dict = {}
	for row in epl_data:
		key = f"{row.voucher_no}-{row.employee}"
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

		voucher_dict[key]['total_tonase'] = 0

	data = []

	for voucher_key, voucher_data in voucher_dict.items():
		if not voucher_data.get('voucher_type') or not voucher_data.get('voucher_no'):
			continue

		voucher_doc = frappe.get_doc(voucher_data.get('voucher_type'), voucher_data.get('voucher_no'))

		if not voucher_data.get('employee'):
			continue

		employee_doc = frappe.get_doc("Employee", voucher_data['employee'])

		kegiatan_doc = None
		if voucher_doc.get('kegiatan'):
			try:
				kegiatan_doc = frappe.get_doc("Kegiatan", voucher_doc.kegiatan)
			except Exception:
				kegiatan_doc = None

		row = {
			'voucher_no': voucher_data.get('voucher_no'),
			'blok': voucher_doc.get('blok', ''),
			'nik': employee_doc.get('no_ktp', ''),
			'employee': voucher_data['employee'],
			'norek_karyawan': employee_doc.get('bank_ac_no', ''),
			'employee_name': employee_doc.get('employee_name', ''),
			'posting_date': voucher_data['posting_date'],
			'kegiatan': voucher_doc.get('kegiatan_account', ''),
			'hasil_kerja_qty': voucher_doc.get('hasil_kerja_qty', 0),
			'brondolan': 0,
			'total_tonase': voucher_data['total_tonase'],
			'satuan': kegiatan_doc.get('uom', '') if kegiatan_doc else '',
			'basis': voucher_doc.get('volume_basis', 0),
			'rupiah_satuan': voucher_doc.get('rupiah_basis', 0),
			'rp_premi': voucher_doc.get('rupiah_premi', 0),
			'kondisi': '',
			'tipe': '',
			'p_upah': voucher_data['p_upah'],
			'p_premi': voucher_data['p_premi'],
			'total': voucher_data['p_upah'] + voucher_data['p_premi'],
			'voucher_type': voucher_data.get('voucher_type')
		}

		data.append(row)

	return data

def get_conditions_epl(filters):
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

def get_panen_data(filters):
	conditions = get_conditions_panen(filters)

	query = """
		SELECT
			bkmp.name as voucher_no,
			dbhkp.blok as blok,
			e.no_ktp as nik,
			dbhkp.employee as employee,
			e.employee_name as employee_name,
			e.bank_ac_no as norek_karyawan,
			bkmp.posting_date as posting_date,
			bkmp.kegiatan_account as kegiatan,
			dbhkp.jumlah_janjang as hasil_kerja_qty,
			bkmp.hasil_kerja_qty_brondolan as brondolan,
			0 as total_tonase,
			k.uom as satuan,
			bkmp.volume_basis as basis,
			bkmp.rupiah_basis as rupiah_satuan,
			0 as rp_premi,
			bkmp.status_panen as kondisi,
			IF(bkmp.manual_hk = 1, 'Manual', '') AS tipe,
			0 as p_upah,
			0 as p_premi,
			0 as total,
			'Buku Kerja Mandor Panen' as voucher_type
		FROM `tabDetail BKM Hasil Kerja Panen` as dbhkp
		JOIN `tabBuku Kerja Mandor Panen` as bkmp ON bkmp.name = dbhkp.parent
		JOIN `tabEmployee` as e ON e.name = dbhkp.employee
		JOIN `tabKegiatan` as k ON k.name = bkmp.kegiatan
		WHERE bkmp.docstatus = 1
		{conditions}
		ORDER BY e.employee_name
	""".format(conditions=conditions)

	rows = frappe.db.sql(query, filters, as_dict=1)

	data = []
	for row in rows:
		data.append({
			'voucher_no': row.voucher_no,
			'blok': row.blok or '',
			'nik': row.nik or '',
			'employee': row.employee,
			'norek_karyawan': row.norek_karyawan or '',
			'employee_name': row.employee_name or '',
			'posting_date': row.posting_date,
			'kegiatan': row.kegiatan or '',
			'hasil_kerja_qty': row.hasil_kerja_qty or 0,
			'brondolan': row.brondolan or 0,
			'total_tonase': row.total_tonase or 0,
			'satuan': row.satuan or '',
			'basis': row.basis or 0,
			'rupiah_satuan': row.rupiah_satuan or 0,
			'rp_premi': row.rp_premi or 0,
			'kondisi': row.kondisi or '',
			'tipe': row.tipe or '',
			'p_upah': row.p_upah or 0,
			'p_premi': row.p_premi or 0,
			'total': row.total or 0,
			'voucher_type': row.voucher_type
		})

	return data

def get_conditions_panen(filters):
	conditions = []

	if filters.get("bulan"):
		bulan_map = {
			"Januari": 1, "Februari": 2, "Maret": 3, "April": 4,
			"Mei": 5, "Juni": 6, "Juli": 7, "Agustus": 8,
			"September": 9, "Oktober": 10, "November": 11, "Desember": 12
		}
		month_num = bulan_map.get(filters.get("bulan"))
		if month_num:
			conditions.append(f"MONTH(bkmp.posting_date) = {month_num}")

	if filters.get("tahun"):
		conditions.append("YEAR(bkmp.posting_date) = %(tahun)s")

	if filters.get("employee"):
		conditions.append("dbhkp.employee = %(employee)s")

	return " AND " + " AND ".join(conditions) if conditions else ""