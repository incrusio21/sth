import frappe

from sth.plantation.doctype.blok.blok import _ensure_blok_cost_center


def execute():
	"""Buat/pastikan Cost Center per-Blok untuk semua Blok yang sudah TM,
	lalu arahkan field cost_center Blok tersebut ke Cost Center itu."""
	bloks = frappe.get_all(
		"Blok",
		filters={"workflow_state": "TM"},
		fields=["name", "unit", "deskripsi", "cost_center"],
	)

	for blok in bloks:
		if not blok.unit or not blok.deskripsi:
			continue

		company = frappe.get_cached_value("Unit", blok.unit, "company")
		if not company:
			continue

		abbr = frappe.get_cached_value("Company", company, "abbr")

		blok_cc = _ensure_blok_cost_center(company, abbr, blok.deskripsi)

		if blok.cost_center != blok_cc:
			frappe.db.set_value("Blok", blok.name, "cost_center", blok_cc, update_modified=False)

	frappe.db.commit()
