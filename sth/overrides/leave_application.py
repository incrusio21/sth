import frappe
from hrms.hr.doctype.leave_application.leave_application import LeaveApplication, get_leave_allocation_records, get_allocation_expiry_for_cf_leaves, get_leaves_for_period, get_remaining_leaves, get_leave_allocation_records, get_leaves_pending_approval_for_period, get_leave_approver, get_leave_balance_on
from datetime import date
import datetime
from frappe.utils import (
	add_days,
	cint,
	cstr,
	date_diff,
	flt,
	formatdate,
	get_fullname,
	get_link_to_form,
	getdate,
	nowdate,
)


class LeaveApplication(LeaveApplication):
	pass

@frappe.whitelist()
def get_leave_balance_on_custom(
	employee: str,
	leave_type: str,
	date: datetime.date,
	to_date: datetime.date | None = None,
	consider_all_leaves_in_the_allocation_period: bool = False,
	for_consumption: bool = False,
):
	if not to_date:
		to_date = nowdate()

	allocation_records = get_leave_allocation_records(employee, date, leave_type)
	allocation = allocation_records.get(leave_type, frappe._dict())

	end_date = allocation.to_date if cint(consider_all_leaves_in_the_allocation_period) else date
	cf_expiry = get_allocation_expiry_for_cf_leaves(employee, leave_type, to_date, allocation.from_date)

	leaves_taken = get_leaves_for_period(employee, leave_type, allocation.from_date, end_date)
	remaining_leaves = get_remaining_leaves(allocation, leaves_taken, date, cf_expiry)

	cuti_bersama = 0

	# Deduct cuti bersama from balance if leave type is Cuti
	if leave_type == "Cuti" and allocation.get("from_date"):
		cuti_bersama = get_cuti_bersama_in_period(
			employee=employee,
			from_date=allocation.from_date,
			to_date=end_date
		)

	if for_consumption:
		return remaining_leaves - cuti_bersama
	else:
		return remaining_leaves.get("leave_balance") - cuti_bersama

def get_cuti_bersama_in_period(employee, from_date, to_date):
	holiday_list = frappe.db.get_value("Employee", employee, "holiday_list")
	if not holiday_list:
		return 0

	if isinstance(from_date, str):
		year_start = f"{from_date[:4]}-01-01"
	else:
		year_start = date(from_date.year, 1, 1)

	return frappe.db.count("Holiday", filters={
		"parent": holiday_list,
		"cuti_bersama": 1,
		"holiday_date": ["between", [year_start, to_date]]
	})

@frappe.whitelist()
def get_leave_details_custom(employee, date, for_salary_slip=False):
	allocation_records = get_leave_allocation_records(employee, date)
	leave_allocation = {}
	precision = cint(frappe.db.get_single_value("System Settings", "float_precision")) or 2

	for d in allocation_records:
		allocation = allocation_records.get(d, frappe._dict())
		to_date = date if for_salary_slip else allocation.to_date
		remaining_leaves = get_leave_balance_on(
			employee,
			d,
			date,
			to_date=to_date,
			consider_all_leaves_in_the_allocation_period=False if for_salary_slip else True,
		)

		leaves_taken = get_leaves_for_period(employee, d, allocation.from_date, to_date) * -1
		leaves_pending = get_leaves_pending_approval_for_period(employee, d, allocation.from_date, to_date)
		expired_leaves = allocation.total_leaves_allocated - (remaining_leaves + leaves_taken)
		cuti_bersama = 0
		if d  == "Cuti" and date:
			cuti_bersama = get_cuti_bersama_in_period(
				employee=employee,
				from_date=date,
				to_date=to_date
			)

		leave_allocation[d] = {
			"total_leaves": flt(allocation.total_leaves_allocated, precision),
			"expired_leaves": flt(expired_leaves, precision) if expired_leaves > 0 else 0,
			"leaves_taken": flt(leaves_taken, precision) + flt(cuti_bersama, precision),
			"leaves_pending_approval": flt(leaves_pending, precision),
			"remaining_leaves": flt(remaining_leaves, precision) - flt(cuti_bersama, precision),
		}
		

	# is used in set query
	lwp = frappe.get_list("Leave Type", filters={"is_lwp": 1}, pluck="name")

	return {
		"leave_allocation": leave_allocation,
		"leave_approver": get_leave_approver(employee),
		"lwps": lwp,
	}
