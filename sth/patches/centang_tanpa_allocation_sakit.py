import json
import os

import frappe

LEAVE_TYPE_TANPA_ALLOCATION = ["Sakit R Jalan", "Sakit R Inap"]


def execute():
	"""Centang Tanpa Allocation pada Leave Type sakit.

	Field-nya disinkronkan dulu: folder custom/ baru diproses bench migrate
	sesudah semua patch.
	"""
	from frappe.modules.utils import sync_customizations_for_doctype

	folder = frappe.get_app_path("sth", "hr_customize", "custom")
	with open(os.path.join(folder, "leave_type.json")) as f:
		sync_customizations_for_doctype(json.load(f), folder)

	frappe.clear_cache(doctype="Leave Type")

	for name in LEAVE_TYPE_TANPA_ALLOCATION:
		if not frappe.db.exists("Leave Type", name):
			print("Leave Type {0} tidak ada, dilewati.".format(name))
			continue

		frappe.db.set_value("Leave Type", name, "tanpa_allocation", 1, update_modified=False)
		print("Tanpa Allocation dicentang pada {0}.".format(name))
