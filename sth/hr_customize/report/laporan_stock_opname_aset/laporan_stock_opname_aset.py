# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	query_l_stock_opname_aset = frappe.db.sql("""
		SELECT
		a.company AS pt,
		a.unit AS unit,
		a.name AS no_aset,
		a.purchase_date AS tahun_perolehan,
		a.gross_purchase_amount AS nilai_aset,
		a.note AS keterangan,
		f.file_url AS foto
		FROM `tabAsset` a
		LEFT JOIN `tabFile` f
		ON f.attached_to_doctype = 'Asset'
		AND f.attached_to_name = a.name
		AND f.attached_to_field = 'image'
		AND f.is_folder = 0
		WHERE a.company IS NOT NULL {};
  """.format(conditions), filters, as_dict=True)

	for asset in query_l_stock_opname_aset:
		data.append(asset)

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("pt"):
		conditions += " AND a.company = %(pt)s"

	if filters.get("unit"):
		conditions += " AND a.unit = %(unit)s"

	if filters.get("status"):
		conditions += " AND a.status = %(status)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("PT"),
			"fieldtype": "Data",
			"fieldname": "pt",
		},
		{
			"label": _("Unit"),
			"fieldtype": "Data",
			"fieldname": "unit",
		},
		{
			"label": _("No Aset"),
			"fieldtype": "Data",
			"fieldname": "no_aset",
		},
		{
			"label": _("No PO/SPK"),
			"fieldtype": "Data",
			"fieldname": "no_po_spk",
		},
		{
			"label": _("Tahun Perolehan"),
			"fieldtype": "Data",
			"fieldname": "tahun_perolehan",
		},
		{
			"label": _("Nilai Aset"),
			"fieldtype": "Currency",
			"fieldname": "nilai_aset",
		},
		{
			"label": _("Tanggal SO Aset"),
			"fieldtype": "Date",
			"fieldname": "tgl_so_aset",
		},
		{
			"label": _("Posisi Aset"),
			"fieldtype": "Data",
			"fieldname": "posisi aset",
		},
		{
			"label": _("Keterangan"),
			"fieldtype": "Data",
			"fieldname": "keterangan",
		},
		{
			"label": _("status"),
			"fieldtype": "Data",
			"fieldname": "status",
		},
		{
			"label": _("Photo"),
			"fieldtype": "Data",
			"fieldname": "photo",
		},
	]

	return columns