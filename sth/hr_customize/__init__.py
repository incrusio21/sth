# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import clear_last_message

def get_overtime_settings(key: str):
	"""Return the value associated with the given `key` from Overtime Settings DocType."""
	if not (system_settings := getattr(frappe.local, "overtime_settings", None)):
		try:
			frappe.local.system_settings = system_settings = frappe.get_cached_doc("Overtime Settings")
		except frappe.DoesNotExistError:  # possible during new install
			clear_last_message()
			return

	return system_settings.get(key)