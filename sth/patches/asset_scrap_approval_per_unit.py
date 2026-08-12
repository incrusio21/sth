import frappe

from sth.accounting_sth.doctype.asset_scrap_settings.asset_scrap_settings import build_workflow


def execute():
	"""Bangun ulang workflow scrap setelah lapis approval bisa diisi per unit.

	Isi setting lama tetap dipakai apa adanya: barisnya tanpa unit, jadi
	semuanya jatuh ke jalur default."""
	if not frappe.get_single("Asset Scrap Settings").lapis_approval:
		return

	build_workflow()
