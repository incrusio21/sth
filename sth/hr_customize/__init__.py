# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import clear_last_message

def get_attendance_settings(key: str):
	"""Return the value associated with the given `key` from Attendance Settings DocType."""
	if not (attendance_setings := getattr(frappe.local, "attendance_setings", None)):
		try:
			frappe.local.attendance_setings = attendance_setings = frappe.get_cached_doc("Attendance Settings")
		except frappe.DoesNotExistError:  # possible during new install
			clear_last_message()
			return

	return attendance_setings.get(key)

def get_premi_attendance_settings(key: str):
	"""Return the value associated with the given `key` from Overtime Settings DocType."""
	if not (premi_attendance_setings := getattr(frappe.local, "premi_attendance_setings", None)):
		premi_type = {}
		for p in get_attendance_settings("premi"):
			premi_type.setdefault(p.premi_type, p.salary_component)

		frappe.local.premi_attendance_setings = premi_attendance_setings = premi_type

	return premi_attendance_setings.get(key)

def get_overtime_settings(key: str):
	"""Return the value associated with the given `key` from Overtime Settings DocType."""
	if not (overtime_settings := getattr(frappe.local, "overtime_settings", None)):
		try:
			frappe.local.overtime_settings = overtime_settings = frappe.get_cached_doc("Overtime Settings")
		except frappe.DoesNotExistError:  # possible during new install
			clear_last_message()
			return

	return overtime_settings.get(key)

def get_payment_settings(key: str):
	"""Return the value associated with the given `key` from Payment Settings DocType."""
	if not (payment_settings := getattr(frappe.local, "payment_settings", None)):
		try:
			frappe.local.payment_settings = payment_settings = frappe.get_cached_doc("Payment Settings")
		except frappe.DoesNotExistError:  # possible during new install
			clear_last_message()
			return

	return payment_settings.get(key)


def get_allowance_settings(key):
	"""Return the value associated with the given `key` from Bonus and Allowance Settings DocType."""
	if not (allowance_settings := getattr(frappe.local, "allowance_settings", None)):
		try:
			frappe.local.allowance_settings = allowance_settings = frappe.get_cached_doc("Bonus and Allowance Settings")
		except frappe.DoesNotExistError:  # possible during new install
			clear_last_message()
			return

	if key:
		return allowance_settings.get(key)
	
	return allowance_settings

@frappe.whitelist()
def update_payment_log(voucher_type, voucher_no=None, filters=None):
	filters = json.loads(filters or "{}")

	if voucher_no:
		filters["name"] = voucher_no

	filters["docstatus"] = 1
	
	for d in frappe.get_all(voucher_type, filters=filters, pluck="name"):
		doc = frappe.get_doc(voucher_type, d)
		doc.run_method("repair_employee_payment_log")

	frappe.msgprint(f"{voucher_type} success to update")