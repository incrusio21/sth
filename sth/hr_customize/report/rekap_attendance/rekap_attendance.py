import frappe
from frappe import _
import calendar
from datetime import datetime, date
from calendar import monthrange
from frappe.utils import add_days, days_diff, flt, getdate, get_first_day_of_week, get_last_day_of_week, month_diff, now, rounded


def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data

def get_columns(filters):
	columns = [
		{
			"fieldname": "employee_name",
			"label": _("Nama"),
			"fieldtype": "Data",
			"width": 200,
			"align": "left"
		}
	]
	
	bulan = filters.get("bulan")
	tahun = filters.get("tahun")
	
	month_map = {
		"Januari": 1, "Februari": 2, "Maret": 3, "April": 4,
		"Mei": 5, "Juni": 6, "Juli": 7, "Agustus": 8,
		"September": 9, "Oktober": 10, "November": 11, "Desember": 12
	}
	
	month_num = month_map.get(bulan, 1)
	num_days = calendar.monthrange(int(tahun), month_num)[1]
	
	for day in range(1, num_days + 1):
		date_obj = datetime(int(tahun), month_num, day)
		
		# if date_obj.weekday() == 6:  # Sunday
		# 	label = f'<span style="color: red;">{day}</span>'
		# else:
		label = str(day)
		
		columns.append({
			"fieldname": f"day_{day}",
			"label": label,
			"fieldtype": "Data",
			"width": 50,
			"align": "center"
		})
	
	status_codes = frappe.get_all("Leave Type",
		filters={"status_code": ["!=", ""]},
		fields=["status_code"],
		order_by="status_code asc",
		group_by="status_code"
	)
	
	summary_cols = [
		{"fieldname": "hke", "label": "HKE", "fieldtype": "Int", "width": 60, "align": "center"},
		{"fieldname": "mg", "label": "MG", "fieldtype": "Int", "width": 60, "align": "center"},
		{"fieldname": "ln", "label": "LN", "fieldtype": "Int", "width": 60, "align": "center"}
	]
	
	for sc in status_codes:
		if sc.status_code:
			summary_cols.append({
				"fieldname": sc.status_code.lower(),
				"label": sc.status_code,
				"fieldtype": "Int",
				"width": 60,
				"align": "center"
			})
	
	summary_cols.append({
		"fieldname": "m",
		"label": "M",
		"fieldtype": "Int",
		"width": 60,
		"align": "center"
	})
	
	columns.extend(summary_cols)
	return columns

def get_all_holidays(year, month_num, num_days):
	"""Get all holidays grouped by holiday_list"""
	holidays = frappe.get_all("Holiday",
		filters={
			"holiday_date": ["between", [
				f"{year}-{month_num:02d}-01",
				f"{year}-{month_num:02d}-{num_days:02d}"
			]]
		},
		fields=["parent", "holiday_date"]
	)
	
	# Group holidays by holiday_list (parent)
	holiday_map = {}
	for holiday in holidays:
		# Exclude Sundays from national holidays
		if holiday.holiday_date.weekday() != 6:
			if holiday.parent not in holiday_map:
				holiday_map[holiday.parent] = set()
			holiday_map[holiday.parent].add(holiday.holiday_date.day)
	
	return holiday_map

def has_presence_in_next_7_days(attendance_dict, start_day, num_days):
	for day in range(start_day + 1, min(start_day + 8, num_days + 1)):
		if day in attendance_dict:
			att = attendance_dict[day]
			if att.status == "Present" or att.status == "On Leave":
				return True
	return False

def get_data(filters):
	"""Get attendance data for all employees"""
	bulan = filters.get("bulan")
	tahun = filters.get("tahun")
	employee = filters.get("employee")
	
	# Convert month name to number (Indonesian)
	month_map = {
		"Januari": 1, "Februari": 2, "Maret": 3, "April": 4,
		"Mei": 5, "Juni": 6, "Juli": 7, "Agustus": 8,
		"September": 9, "Oktober": 10, "November": 11, "Desember": 12
	}
	
	month_num = month_map.get(bulan, 1)
	year = int(tahun)
	num_days = calendar.monthrange(year, month_num)[1]
	
	# Get current date for comparison
	today = date.today()
	
	# Get all holidays once
	holiday_map = get_all_holidays(year, month_num, num_days)
	
	employee_filters = {"status": "Active"}
	if employee:
		employee_filters["name"] = employee
	
	employees = frappe.get_all("Employee", 
		filters=employee_filters,
		fields=["name", "employee_name", "employment_type", "holiday_list", "designation"],
		order_by="employee_name"
	)
	
	status_codes = frappe.get_all("Leave Type",
		filters={"status_code": ["!=", ""]},
		fields=["status_code"],
		order_by="status_code asc"
	)
	
	# Get all leave types once
	leave_types = frappe.get_all("Leave Type",
		fields=["name", "status_code"]
	)
	leave_type_map = {}
	for lt in leave_types:
		leave_type_map[lt.name] = lt.status_code
	
	data = []
	
	for emp in employees:
		row = {
			"employee_name": emp.employee_name,
			"hke": 0,
			"mg": 0,
			"ln": 0,
			"m": 0,
			"l": 0
		}
		
		for sc in status_codes:
			if sc.status_code:
				row[sc.status_code.lower()] = 0
		
		# Get holiday dates for this employee from pre-loaded map
		holiday_dates = holiday_map.get(emp.holiday_list, set())
		
		attendances = frappe.get_all("Attendance",
			filters={
				"employee": emp.name,
				"attendance_date": ["between", [
					f"{year}-{month_num:02d}-01",
					f"{year}-{month_num:02d}-{num_days:02d}"
				]]
			},
			fields=["attendance_date", "status", "leave_type"]
		)
	
		attendance_dict = {}
		for att in attendances:
			day = att.attendance_date.day
			attendance_dict[day] = att
		
		is_karyawan_tetap = emp.employment_type == "KARYAWAN TETAP"
		
		adakah_attendance_di_bulan_ini = 0
		for day in range(1, num_days + 1):
			date_obj = datetime(year, month_num, day)
			day_of_week = date_obj.weekday()
			current_date = date_obj.date()
			
			status = ""	
			# Check if it's a national holiday (non-Sunday)
			if day in holiday_dates and current_date <= today and (is_karyawan_tetap or (not is_karyawan_tetap and day not in attendance_dict)):
				status = '<span style="color: red;">LN</span>'
				row["ln"] += 1
			# Only show MG if the date has passed and it's not a national holiday
			elif day_of_week == 6 and emp.designation != "NS30" :  # Sunday

				end_date = getdate(current_date)
				last_day_of_month = monthrange(year, month_num)[1]

				is_last_sunday_of_the_month = (
					end_date.day == last_day_of_month and 
					end_date.weekday() == 6  # Sunday = 6
				)

				if (current_date <= today and has_presence_in_next_7_days(attendance_dict, day, num_days)) or (is_last_sunday_of_the_month and adakah_attendance_di_bulan_ini == 1):	
					# kalau bukan satpam
					status = '<span style="color: red;">MG</span>'
					row["mg"] += 1

				# else: leave empty for future Sundays
			elif day in attendance_dict:
				att = attendance_dict[day]
				adakah_attendance_di_bulan_ini = 1

				if att.leave_type and att.leave_type in leave_type_map:

					status_code = leave_type_map[att.leave_type]
					if status_code:
						status = status_code
						if status_code.lower() in row:
							row[status_code.lower()] += 1
							
				elif att.status == "Present":
					status = "H"
					row["hke"] += 1
				
				elif att.status == "Absent":
					status = "M"
					row["m"] += 1

				elif att.status == "7th Day Off":
					status = '<span style="color: red;">L</span>'
					row["l"] += 1
			
			row[f"day_{day}"] = status
		
		data.append(row)
	
	return data