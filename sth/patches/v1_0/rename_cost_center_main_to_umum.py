import frappe


def execute():
	"""Rename every Cost Center named "Main" (per company) to "UMUM"."""
	cost_centers = frappe.get_all(
		"Cost Center",
		filters={"cost_center_name": "Main"},
		fields=["name", "company"],
	)

	for cost_center in cost_centers:
		abbr = frappe.db.get_value("Company", cost_center.company, "abbr")
		new_name = f"UMUM - {abbr}" if abbr else "UMUM"

		if frappe.db.exists("Cost Center", new_name):
			continue

		frappe.rename_doc("Cost Center", cost_center.name, new_name, force=True)
