import frappe
from frappe import _
from frappe.utils import getdate, today, get_first_day, get_last_day, add_days, add_years
from datetime import datetime, timedelta

def calculate_allocation_period(employee, current_date, grade):
	"""
	Calculate allocation period based on employee joining date and grade.
	Returns (from_date, to_date, should_allocate)
	"""
	joining_date = getdate(employee.date_of_joining) if employee.date_of_joining else None
	current_date = getdate(current_date)
	
	if not joining_date:
		return None, None, False
	
	# Employee must have been employed for at least 1 year
	one_year_after_joining = add_years(joining_date, 1)
	
	if current_date < one_year_after_joining:
		return None, None, False
	
	if grade == "NON STAF":
		# Anniversary-based allocation
		# Calculate which anniversary period we're in
		years_since_joining = current_date.year - joining_date.year
		if (current_date.month, current_date.day) < (joining_date.month, joining_date.day):
			years_since_joining -= 1
		
		# Anniversary date for current period
		anniversary_date = joining_date.replace(year=joining_date.year + years_since_joining)
		
		# Ensure we're past the first year
		if anniversary_date < one_year_after_joining:
			anniversary_date = one_year_after_joining
		
		from_date = anniversary_date
		to_date = add_days(add_years(anniversary_date, 1), -1)
		
		# Check if current date is exactly the anniversary date
		if current_date == from_date:
			return from_date, to_date, True
		else:
			return from_date, to_date, False
		
	else:
		# Calendar year allocation for non-NON STAF employees
		# Check if employee has completed 1 year
		year_start = getdate(f"{current_date.year}-01-01")
		
		# If joining + 1 year is after year start, use joining + 1 year as start
		if one_year_after_joining > year_start:
			# Not yet eligible for calendar year allocation
			# Check if today is exactly 1 year after joining
			if current_date == one_year_after_joining:
				from_date = one_year_after_joining
				to_date = getdate(f"{current_date.year}-12-31")
				return from_date, to_date, True
			else:
				return None, None, False
		else:
			# Eligible for calendar year allocation
			# Check if today is January 1st
			if current_date.month == 1 and current_date.day == 1:
				from_date = year_start
				to_date = getdate(f"{current_date.year}-12-31")
				return from_date, to_date, True
			else:
				return None, None, False


def create_daily_leave_allocations():
	"""
	Run daily to check and create leave allocations for eligible employees.
	This should be called by the daily cron job.
	"""
	current_date = today()
	
	leave_policies = frappe.get_all(
		"Leave Policy",
		filters={"create_leave_allocation_annually": 1, "docstatus" :1},
		fields=["name"]
	)
	
	if not leave_policies:
		return
	
	employees = frappe.get_all(
		"Employee",
		filters={"status": "Active"},
		fields=["name", "employee_name", "employment_type", "grade", "date_of_joining"]
	)
	
	if not employees:
		return
	
	total_created = 0
	
	for policy in leave_policies:
		policy_doc = frappe.get_doc("Leave Policy", policy.name)
		
		for policy_detail in policy_doc.leave_policy_details:
			leave_type = policy_detail.leave_type
			annual_allocation = policy_detail.annual_allocation
			
			matching_employees = [
				emp for emp in employees
				if (policy_detail.employment_type == "" or emp.employment_type == policy_detail.employment_type)
				and emp.grade == policy_detail.grade
			]
			
			for employee in matching_employees:
				try:
					from_date, to_date, should_allocate = calculate_allocation_period(
						employee, current_date, employee.grade
					)
					
					if not should_allocate:
						continue
					
					# Check if allocation already exists
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
						continue
					
					# Create the allocation
					leave_allocation = frappe.get_doc({
						"doctype": "Leave Allocation",
						"employee": employee.name,
						"employee_name": employee.employee_name,
						"leave_type": leave_type,
						"from_date": from_date,
						"to_date": to_date,
						"new_leaves_allocated": annual_allocation,
						"leave_policy": policy_doc.name,
						"leave_policy_assignment": None,
						"description": f"Auto-allocated from Leave Policy: {policy_doc.name} ({'Anniversary-based' if employee.grade == 'NON STAF' else 'Calendar year'})"
					})
					
					leave_allocation.insert(ignore_permissions=True)
					leave_allocation.submit()
					
					total_created += 1
					
					frappe.logger().info(f"Created leave allocation for {employee.name} ({employee.grade}): {from_date} to {to_date}")
					
				except Exception as e:
					frappe.log_error(
						message=f"Error creating leave allocation for {employee.name}: {str(e)}",
						title="Daily Leave Allocation Error"
					)
	
	if total_created > 0:
		frappe.logger().info(f"Daily leave allocation: Created {total_created} new allocations")


def create_annual_leave_allocations(doc, method=None, assigned_year=None):
	"""
	Manual trigger to create allocations for a specific year.
	This is kept for backward compatibility and manual execution.
	"""
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
	allocations_not_eligible = 0
	
	for policy_detail in doc.leave_policy_details:
		leave_type = policy_detail.leave_type
		annual_allocation = policy_detail.annual_allocation
		
		matching_employees = [
			emp for emp in employees
			if (policy_detail.employment_type == "" or emp.employment_type == policy_detail.employment_type)
			and emp.grade == policy_detail.grade
		]
		
		for employee in matching_employees:
			try:
				# For manual execution, we create allocations based on current year
				current_date = getdate(year_start)
				from_date, to_date, _ = calculate_allocation_period(
					employee, current_date, employee.grade
				)
				
				if from_date is None:
					allocations_not_eligible += 1
					continue
				
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
				
				leave_allocation = frappe.get_doc({
					"doctype": "Leave Allocation",
					"employee": employee.name,
					"employee_name": employee.employee_name,
					"leave_type": leave_type,
					"from_date": from_date,
					"to_date": to_date,
					"new_leaves_allocated": annual_allocation,
					"leave_policy": doc.name,
					"leave_policy_assignment": None,
					"description": f"Auto-allocated from Leave Policy: {doc.name} ({'Anniversary-based' if employee.grade == 'NON STAF' else 'Calendar year'})"
				})
				
				leave_allocation.insert(ignore_permissions=True)
				leave_allocation.submit()
				
				allocations_created += 1
				
			except Exception as e:
				frappe.log_error(
					message=f"Error creating leave allocation for {employee.name}: {str(e)}",
					title="Leave Allocation Creation Error"
				)
	
	message_parts = []
	if allocations_created > 0:
		message_parts.append(f"Created {allocations_created} allocations")
	if allocations_skipped > 0:
		message_parts.append(f"{allocations_skipped} skipped (already exist)")
	if allocations_not_eligible > 0:
		message_parts.append(f"{allocations_not_eligible} not eligible (< 1 year joining date)")
	
	# if allocations_created > 0:
	# 	if message_parts:
	# 		frappe.msgprint(
	# 			_(". ".join(message_parts)),
	# 			indicator="green"
	# 		)
	# else:
	# 	if message_parts:
	# 		frappe.msgprint(
	# 			_(". ".join(message_parts) if message_parts else "No allocations created"),
	# 			indicator="blue"
	# 		)


def create_allocations_for_new_employee(doc, method=None):
	"""
	Create leave allocation immediately when a new employee is created,
	if they are eligible (>= 1 year from joining date).
	This runs once when employee is saved.
	"""
	if doc.is_new() or not doc.employment_type or not doc.grade:
		return
	
	current_date = getdate()
	
	leave_policies = frappe.get_all(
		"Leave Policy",
		filters={"create_leave_allocation_annually": 1, "docstatus" : 1},
		fields=["name"]
	)
	
	allocations_created = 0
	
	for policy in leave_policies:
		policy_doc = frappe.get_doc("Leave Policy", policy.name)
		
		for policy_detail in policy_doc.leave_policy_details:
			if ((policy_detail.employment_type == "" or policy_detail.employment_type == doc.employment_type) and 
				policy_detail.grade == doc.grade):
				
				from_date, to_date, should_allocate = calculate_allocation_period(
					doc, current_date, doc.grade
				)
				
				# For new employee, check if they're eligible (>= 1 year)
				# Even if today is not their allocation date, create if eligible
				if from_date is None:
					continue
				
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
				
				# Only create if today is the allocation date OR if we're past the allocation date
				joining_date = getdate(doc.date_of_joining)
				one_year_after = add_years(joining_date, 1)
				
				# Skip if not yet eligible (less than 1 year)
				if current_date < one_year_after:
					continue
				
				# For NON STAF: create if we're on or past the anniversary
				# For others: create if we're on or past Jan 1 (and >= 1 year from joining)
				should_create = False
				
				if doc.grade == "NON STAF":
					# Check if current date is on or past the current anniversary period start
					if current_date >= from_date:
						should_create = True
				else:
					# For non-NON STAF, create if:
					# 1. We're past 1 year from joining
					# 2. We're in the current year allocation period
					year_start = getdate(f"{current_date.year}-01-01")
					if one_year_after <= year_start:
						# Use calendar year
						if current_date >= year_start:
							should_create = True
					else:
						# First allocation is from 1-year-after-joining to year-end
						if current_date >= one_year_after:
							should_create = True
				
				if not should_create:
					continue
				
				try:
					leave_allocation = frappe.get_doc({
						"doctype": "Leave Allocation",
						"employee": doc.name,
						"employee_name": doc.employee_name,
						"leave_type": policy_detail.leave_type,
						"from_date": from_date,
						"to_date": to_date,
						"new_leaves_allocated": policy_detail.annual_allocation,
						"leave_policy": policy_doc.name,
						"description": f"Auto-allocated from Leave Policy: {policy_doc.name} (New Employee)"
					})
					
					leave_allocation.insert(ignore_permissions=True)
					leave_allocation.submit()
					
					allocations_created += 1
					
					frappe.logger().info(f"Created leave allocation for new employee {doc.name}: {from_date} to {to_date}")
					
				except Exception as e:
					frappe.log_error(
						message=f"Error creating leave allocation for new employee {doc.name}: {str(e)}",
						title="New Employee Leave Allocation Error"
					)

def debug():
	"""Run test in Frappe console"""
	test_allocation_logic()


def debug_la():
    doc = frappe.get_doc("Leave Policy","HR-LPOL-2026-00003")
    create_annual_leave_allocations(doc, "validate", 2025)