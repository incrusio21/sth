# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import clear_last_message

def get_plantation_settings(key: str):
	"""Return the value associated with the given `key` from Plantation Settings DocType."""
	if not (plantation_settings := getattr(frappe.local, "plantation_settings", None)):
		try:
			frappe.local.plantation_settings = plantation_settings = frappe.get_cached_doc("Plantation Settings")
		except frappe.DoesNotExistError:  # possible during new install
			clear_last_message()
			return

	return plantation_settings.get(key)