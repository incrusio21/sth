# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import clear_last_message

def get_legal_settings(key):
	"""Return the value associated with the given `key` from Legal Settings DocType."""
	if not (legal_settings := getattr(frappe.local, "legal_settings", None)):
		try:
			frappe.local.legal_settings = legal_settings = frappe.get_cached_doc("Legal Settings")
		except frappe.DoesNotExistError:  # possible during new install
			clear_last_message()
			return

	if key:
		return legal_settings.get(key)
	
	return legal_settings