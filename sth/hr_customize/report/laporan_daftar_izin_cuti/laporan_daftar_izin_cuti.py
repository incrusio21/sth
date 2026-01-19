# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from hrms.hr.doctype.leave_application.leave_application import get_leave_allocation_records
from frappe.utils import flt, cint, getdate, nowdate, get_last_day, add_days

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	query_l_daftar_izin_cuti = frappe.db.sql("""
		SELECT
		la.company as pt,
		e.unit as unit,
		e.employee_name as nama,
		e.grade as golongan,
		e.employment_type as level,
		la.leave_type as jenis_izin_cuti,
		la.from_date as tgl_awal,
		la.to_date as tgl_berakhir_cuti,
		la.total_leaves_allocated as jumlah_hk,
		la.employee
		FROM `tabLeave Allocation` as la
		JOIN `tabEmployee` as e ON e.name = la.employee
		WHERE la.company IS NOT NULL
		AND la.docstatus = 1
		 {};
	""".format(conditions), filters, as_dict=True)

	for leave in query_l_daftar_izin_cuti:

		# leave_details = get_leave_details_unrestricted(employee=leave.employee,date=frappe.utils.today())
		leave_details = get_leave_details_unrestricted(employee=leave.employee,date=leave.tgl_berakhir_cuti)

		sisa = 0
		if leave.jenis_izin_cuti in leave_details["leave_allocation"]:
			sisa = leave_details["leave_allocation"][leave.jenis_izin_cuti]["remaining_leaves"]


		data.append({
			"pt": leave.pt,
			"unit": leave.unit,
			"nama": leave.nama,
			"golongan": leave.golongan,
			"level": leave.level,
			"jenis_izin_cuti": leave.jenis_izin_cuti,
			"tgl_awal": leave.tgl_awal,
			"tgl_berakhir_cuti": leave.tgl_berakhir_cuti,
			"jumlah_hk": leave.jumlah_hk,
			"hk": sisa
		})

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("jenis_izin_cuti"):
		conditions += " AND la.leave_type = %(jenis_izin_cuti)s"

	if filters.get("pt"):
		conditions += " AND la.company = %(pt)s"

	if filters.get("unit"):
		conditions += " AND e.unit = %(unit)s"

	if filters.get("golongan"):
		conditions += " AND e.grade = %(golongan)s"

	if filters.get("level"):
		conditions += " AND e.employment_type = %(level)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("PT"),
			"fieldtype": "Data",
			"fieldname": "pt",
		},
		{
			"label": _("Unit"),
			"fieldtype": "Data",
			"fieldname": "unit",
		},
		{
			"label": _("Nama"),
			"fieldtype": "Data",
			"fieldname": "nama",
			"width": 300
		},
		{
			"label": _("Golongan"),
			"fieldtype": "Data",
			"fieldname": "golongan",
		},
		{
			"label": _("Level"),
			"fieldtype": "Data",
			"fieldname": "level",
		},
		{
			"label": _("Jenis Izin Cuti"),
			"fieldtype": "Data",
			"fieldname": "jenis_izin_cuti",
		},
		{
			"label": _("Tgl Awal"),
			"fieldtype": "Data",
			"fieldname": "tgl_awal",
		},
		{
			"label": _("Tgl Berakhir Cuti"),
			"fieldtype": "Data",
			"fieldname": "tgl_berakhir_cuti",
		},
		{
			"label": _("Total Cuti"),
			"fieldtype": "Data",
			"fieldname": "jumlah_hk",
		},
		{
			"label": _("Sisa Cuti"),
			"fieldtype": "Data",
			"fieldname": "hk",
		},
	]

	return columns

@frappe.whitelist()
def get_leave_details_unrestricted(employee, date, for_salary_slip=False):

	allocation_records = get_leave_allocation_records(employee, date)
	leave_allocation = {}
	precision = cint(frappe.db.get_single_value("System Settings", "float_precision")) or 2

	for d in allocation_records:
		allocation = allocation_records.get(d, frappe._dict())
		to_date = date if for_salary_slip else allocation.to_date

		remaining_leaves = frappe.call(
			"hrms.hr.doctype.leave_application.leave_application.get_leave_balance_on",
			employee=employee,
			leave_type=d,
			date=date,
			to_date=to_date,
			consider_all_leaves_in_the_allocation_period=not for_salary_slip
		)

		leaves_taken = frappe.call(
			"hrms.hr.doctype.leave_application.leave_application.get_leaves_for_period",
			employee=employee,
			leave_type=d,
			from_date=allocation.from_date,
			to_date=to_date
		) * -1

		leaves_pending = frappe.call(
			"hrms.hr.doctype.leave_application.leave_application.get_leaves_pending_approval_for_period",
			employee=employee,
			leave_type=d,
			from_date=allocation.from_date,
			to_date=to_date
		)

		expired_leaves = allocation.total_leaves_allocated - (remaining_leaves + leaves_taken)

		leave_allocation[d] = {
			"total_leaves": flt(allocation.total_leaves_allocated, precision),
			"expired_leaves": flt(expired_leaves, precision) if expired_leaves > 0 else 0,
			"leaves_taken": flt(leaves_taken, precision),
			"leaves_pending_approval": flt(leaves_pending, precision),
			"remaining_leaves": flt(remaining_leaves, precision),
		}

	lwp = frappe.db.get_list(
		"Leave Type",
		filters={"is_lwp": 1},
		pluck="name",
		ignore_permissions=True,
	)

	return {
		"leave_allocation": leave_allocation,
		"leave_approver": frappe.call(
			"hrms.hr.doctype.leave_application.leave_application.get_leave_approver",
			employee=employee
		),
		"lwps": lwp,
	}

def get_effective_date(filters):
    
    today = getdate(nowdate())
    
    if filters.get("periode"):
        fiscal_year = frappe.get_doc("Fiscal Year", filters.get("periode"))
        fiscal_year_end = getdate(fiscal_year.year_end_date)
        
        # If today is greater than fiscal year end, use fiscal year end date
        if today > fiscal_year_end:
            return fiscal_year_end
        else:
            return today

@frappe.whitelist()
def debug():
	get_leave_details_unrestricted("HR-EMP-00701","2025-12-31")