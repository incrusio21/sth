import frappe
from frappe import _
from frappe.utils import flt, getdate
from datetime import datetime, timedelta
import calendar

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	return [
		{
			"label": _("No Transaksi"),
			"fieldname": "no_transaksi",
			"fieldtype": "Link",
			"options": "Attendance",
			"width": 200,
			"align": "left"
		},
		{
			"label": _("Divisi"),
			"fieldname": "divisi",
			"fieldtype": "Data",
			"width": 150,
			"align": "left"
		},
		{
			"label": _("Nama Karyawan"),
			"fieldname": "nama_karyawan",
			"fieldtype": "Data",
			"width": 350
		},
		{
			"label": _("Tanggal"),
			"fieldname": "tanggal",
			"fieldtype": "Date",
			"width": 120
		},
		{
			"label": _("Kegiatan"),
			"fieldname": "kegiatan",
			"fieldtype": "Data",
			"width": 420
		},
		{
			"label": _("Absensi"),
			"fieldname": "absensi",
			"fieldtype": "Data",
			"width": 100
		},
		{
			"label": _("Gaji Pokok"),
			"fieldname": "gaji_pokok",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": _("Premi Kehadiran"),
			"fieldname": "premi_kehadiran",
			"fieldtype": "Currency",
			"width": 150
		},
		{
			"label": _("Total"),
			"fieldname": "total",
			"fieldtype": "Currency",
			"width": 120
		}
	]

def get_data(filters):
	bulan_map = {
		"Januari": 1, "Februari": 2, "Maret": 3, "April": 4,
		"Mei": 5, "Juni": 6, "Juli": 7, "Agustus": 8,
		"September": 9, "Oktober": 10, "November": 11, "Desember": 12
	}
	month_num = bulan_map.get(filters.get("bulan"), 1)
	year = int(filters.get("tahun"))
	
	# Get all employees who have attendance in the selected month
	employee_list = get_employees_with_attendance(filters, month_num, year)
	
	if not employee_list:
		return []
	
	result = []
	
	# Process each employee
	for employee_id in employee_list:
		employee_data = process_employee(employee_id, filters, month_num, year)
		result.extend(employee_data)
	
	return result

def get_employees_with_attendance(filters, month_num, year):
	"""Get list of employees who have attendance in the selected month"""
	
	# If employee filter is provided, use only that employee
	if filters.get("employee"):
		employee_doc = frappe.get_doc("Employee", filters.get("employee"))
		if employee_doc.custom_kriteria == "Satuan Hasil":
			frappe.throw(""" Employee dengan kriteria Satuan Hasil tidak boleh muncul di Laporan ini. """)

		return [filters.get("employee")]
	
	# Otherwise, get all employees with attendance in that month
	query = """
		SELECT DISTINCT 
			a.employee
		FROM 
			`tabAttendance` a
		JOIN `tabEmployee` b
			ON a.employee = b.name AND b.custom_kriteria = "Non Satuan Hasil"
		WHERE 
			a.docstatus = 1
			AND MONTH(a.attendance_date) = %(month)s
			AND YEAR(a.attendance_date) = %(year)s
			
		ORDER BY 
			a.employee
	"""
	
	employees = frappe.db.sql(query, {
		"month": month_num,
		"year": year
	}, as_dict=1)
	
	return [emp.employee for emp in employees]

def process_employee(employee_id, filters, month_num, year):
	"""Process attendance and salary data for a single employee"""
	
	employee = frappe.get_doc("Employee", employee_id)
	ump_bulanan = frappe.get_doc("Company", employee.company).ump_bulanan 
	hari_ump = frappe.get_doc("Employment Type", employee.employment_type).hari_ump
	
	num_days = calendar.monthrange(year, month_num)[1]
	all_dates = [datetime(year, month_num, day).date() for day in range(1, num_days + 1)]

	# Get Employee Payment Log for Premi Kehadiran
	epl = frappe.qb.DocType("Employee Payment Log")
	emp_pl = (
		frappe.qb.from_(epl)
		.select(epl.posting_date, epl.amount)
		.where(
			(epl.employee == employee_id)
			& (epl.salary_component == "Premi Kehadiran")
			& (epl.posting_date.isin(all_dates))
		)
	).run(as_dict=1)

	# Get holidays for the employee
	holiday_query = """
		SELECT 
			holiday_date
		FROM 
			`tabHoliday`
		WHERE 
			MONTH(holiday_date) = %(month)s
			AND YEAR(holiday_date) = %(year)s
			AND parent IN (
				SELECT holiday_list 
				FROM `tabEmployee` 
				WHERE name = %(employee)s
			)
	"""	

	holidays = frappe.db.sql(holiday_query, {
		"employee": employee_id,
		"month": month_num,
		"year": year
	}, as_dict=1)
	
	holiday_dates = {getdate(h.holiday_date) for h in holidays}

	# Get attendance data
	attendance_query = """
		SELECT 
			a.name as no_transaksi,
			a.attendance_date as tanggal,
			a.status_code as absensi
		FROM 
			`tabAttendance` a
		WHERE 
			a.docstatus = 1
			AND a.employee = %(employee)s
			AND MONTH(a.attendance_date) = %(month)s
			AND YEAR(a.attendance_date) = %(year)s
		ORDER BY 
			a.attendance_date
	"""
	
	attendance_data = frappe.db.sql(attendance_query, {
		"employee": employee_id,
		"month": month_num,
		"year": year
	}, as_dict=1)

	attendance_dict = {getdate(row.tanggal): row for row in attendance_data}
	
	result = []
	total_gaji_pokok = 0
	total_premi_kehadiran = 0
	total_amount = 0
	
	# Process each date in the month
	for date in all_dates:
		attendance_row = attendance_dict.get(date)
		
		if attendance_row:
			no_transaksi = attendance_row.no_transaksi
			absensi = attendance_row.absensi
		else:
			no_transaksi = ""
			if date.weekday() == 6:
				absensi = "MG"  
			elif date in holiday_dates:
				absensi = "LN" 
			else:
				absensi = ""

		gaji_pokok = 0
		if absensi != "":
			gaji_pokok = ump_bulanan / hari_ump 

		premi_kehadiran = 0
		for check_premi in emp_pl:
			if check_premi.posting_date == date:
				premi_kehadiran = check_premi.amount

		total = gaji_pokok + premi_kehadiran
		
		result.append({
			"no_transaksi": no_transaksi,
			"divisi": employee.custom_divisi or "",
			"nama_karyawan": employee.employee_name,
			"tanggal": date,
			"kegiatan": "7111102-UPAH (NON-STAF) - KANTOR, UMUM DAN KEAMANAN",
			"absensi": absensi,
			"gaji_pokok": gaji_pokok,
			"premi_kehadiran": premi_kehadiran,
			"total": total
		})
		
		total_gaji_pokok += gaji_pokok
		total_premi_kehadiran += premi_kehadiran
		total_amount += total
	
	# Add total row for this employee
	result.append({
		"no_transaksi": "",
		"divisi": "",
		"nama_karyawan": f"<b>Total {employee.employee_name}</b>",
		"tanggal": "",
		"kegiatan": "",
		"absensi": "",
		"gaji_pokok": total_gaji_pokok,
		"premi_kehadiran": total_premi_kehadiran,
		"total": total_amount
	})
	
	return result