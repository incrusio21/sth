# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe


@frappe.whitelist()
def get_cost_center_from_divisi(sub_unit, company):
	"""Resolve Cost Center for a Sub Unit (Divisi): use Divisi.cost_center if set, else fall back to the company's UMUM cost center."""
	if not sub_unit:
		return None

	cost_center = frappe.db.get_value("Divisi", sub_unit, "cost_center")
	if cost_center:
		return cost_center

	abbr = frappe.db.get_value("Company", company, "abbr")
	if not abbr:
		return None

	umum_cost_center = f"UMUM - {abbr}"
	if frappe.db.exists("Cost Center", umum_cost_center):
		return umum_cost_center

	return None
