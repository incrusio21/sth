import frappe
from frappe import _
from frappe.utils import getdate, today, get_first_day, get_last_day, add_days
from datetime import datetime

def create_annual_leave_allocations(doc, method=None, assigned_year=None):
	if not doc.create_leave_allocation_annually:
		return
	
	current_year = datetime.now().year
	if assigned_year:
		current_year = assigned_year

	year_start = f"{current_year}-01-01"
	year_end = f"{current_year}-12-31"
	
	employees = frappe.get_all(
		"Employee",
		filters={"status": "Active"},
		fields=["name", "employee_name", "employment_type", "grade", "date_of_joining"]
	)
	
	if not employees:
		frappe.msgprint(_("No active employees found"))
		return
	
	allocations_created = 0
	allocations_skipped = 0
	
	for policy_detail in doc.leave_policy_details:
		leave_type = policy_detail.leave_type
		annual_allocation = policy_detail.annual_allocation
		
		matching_employees = [
			emp for emp in employees
			if emp.employment_type == policy_detail.employment_type
			and emp.grade == policy_detail.grade
		]
		
		for employee in matching_employees:
			try:
				joining_date = getdate(employee.date_of_joining) if employee.date_of_joining else None
				
				if joining_date and joining_date > getdate(year_start):
					from_date = joining_date
				else:
					from_date = getdate(year_start)
				
				to_date = getdate(year_end)
				
				existing_allocation = frappe.db.exists(
					"Leave Allocation",
					{
						"employee": employee.name,
						"leave_type": leave_type,
						"from_date": from_date,
						"to_date": to_date,
						"docstatus": ["!=", 2]
					}
				)
				
				if existing_allocation:
					allocations_skipped += 1
					continue
				
				allocated_leaves = annual_allocation
				if joining_date and joining_date > getdate(year_start):

					total_days = (getdate(year_end) - getdate(year_start)).days + 1
					remaining_days = (getdate(year_end) - from_date).days + 1
					allocated_leaves = (annual_allocation * remaining_days) / total_days
					allocated_leaves = round(allocated_leaves)
				
				leave_allocation = frappe.get_doc({
					"doctype": "Leave Allocation",
					"employee": employee.name,
					"employee_name": employee.employee_name,
					"leave_type": leave_type,
					"from_date": from_date,
					"to_date": to_date,
					"new_leaves_allocated": allocated_leaves,
					"leave_policy": doc.name,
					"leave_policy_assignment": None,  
					"description": f"Auto-allocated from Leave Policy: {doc.name}"
				})
				
				leave_allocation.insert(ignore_permissions=True)
				leave_allocation.submit()
				
				allocations_created += 1
				
			except Exception as e:
				frappe.log_error(
					message=f"Error creating leave allocation for {employee.name}: {str(e)}",
					title="Leave Allocation Creation Error"
				)
	
	if allocations_created > 0:
		frappe.msgprint(
			_("Successfully created {0} leave allocations. {1} skipped (already exist)").format(
				allocations_created, allocations_skipped
			),
			indicator="green"
		)
	else:
		frappe.msgprint(
			_("No new allocations created. {0} allocations already exist.").format(allocations_skipped),
			indicator="blue"
		)


def create_allocations_for_new_employee(doc, method=None):
	if doc.is_new() or not doc.employment_type or not doc.grade:
		return
	
	current_year = datetime.now().year
	year_start = f"{current_year}-01-01"
	year_end = f"{current_year}-12-31"
	
	leave_policies = frappe.get_all(
		"Leave Policy",
		filters={"create_leave_allocation_annually": 1},
		fields=["name"]
	)
	
	for policy in leave_policies:
		policy_doc = frappe.get_doc("Leave Policy", policy.name)
		
		for policy_detail in policy_doc.leave_policy_details:
			if (policy_detail.employment_type == doc.employment_type and 
				policy_detail.grade == doc.grade):
				
				joining_date = getdate(doc.date_of_joining) if doc.date_of_joining else None
				
				if joining_date and joining_date > getdate(year_start):
					from_date = joining_date
				else:
					from_date = getdate(year_start)
				
				to_date = getdate(year_end)
				
				existing_allocation = frappe.db.exists(
					"Leave Allocation",
					{
						"employee": doc.name,
						"leave_type": policy_detail.leave_type,
						"from_date": from_date,
						"to_date": to_date,
						"docstatus": ["!=", 2]
					}
				)
				
				if existing_allocation:
					continue
				
				allocated_leaves = policy_detail.annual_allocation
				if joining_date and joining_date > getdate(year_start):
					total_days = (getdate(year_end) - getdate(year_start)).days + 1
					remaining_days = (getdate(year_end) - from_date).days + 1
					allocated_leaves = (policy_detail.annual_allocation * remaining_days) / total_days
					allocated_leaves = round(allocated_leaves)
				
				try:
					leave_allocation = frappe.get_doc({
						"doctype": "Leave Allocation",
						"employee": doc.name,
						"employee_name": doc.employee_name,
						"leave_type": policy_detail.leave_type,
						"from_date": from_date,
						"to_date": to_date,
						"new_leaves_allocated": allocated_leaves,
						"leave_policy": policy_doc.name,
						"description": f"Auto-allocated from Leave Policy: {policy_doc.name}"
					})
					
					leave_allocation.insert(ignore_permissions=True)
					leave_allocation.submit()
					
				except Exception as e:
					frappe.log_error(
						message=f"Error creating leave allocation: {str(e)}",
						title="Leave Allocation Error"
					)


def run_annual_allocation():
	leave_policies = frappe.get_all(
		"Leave Policy",
		filters={"create_leave_allocation_annually": 1},
		fields=["name"]
	)
	
	for policy in leave_policies:
		policy_doc = frappe.get_doc("Leave Policy", policy.name)
		create_annual_leave_allocations(policy_doc)

def debug():
	doc = frappe.get_doc("Leave Policy","HR-LPOL-2026-00001")
	create_annual_leave_allocations(doc,"validate",2025)
