# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)

	query_l_ppn_masukan = frappe.db.sql(f"""
		SELECT
			pi.supplier_name as nama_vendor,
			nvm.coa as kode_akun,
			pi.total - pi.discount_amount as dpp,
			pi.total_pph_lainnya as pph,
			pi.total_ppn as ppn,
			pi.name as no_invoice,
			pi.no_fp as no_faktur,
			pi.no_faktur_pajak_pengganti as no_faktur_pengganti,
			pi.posting_date as tanggal_invoice,
			GROUP_CONCAT(DISTINCT vd.type SEPARATOR ', ') as jenis_pajak,
			pi.total_pph_lainnya as summary_all_pph
		FROM `tabPurchase Invoice` pi
		LEFT JOIN `tabNon Voucher Match` nvm 
			ON nvm.parent = pi.name
			AND nvm.pph != 0
		LEFT JOIN `tabVAT Detail` vd
			ON vd.parent = pi.name
		WHERE pi.company IS NOT NULL
		{conditions}
		GROUP BY pi.name
	""", filters, as_dict=True)

	return columns, query_l_ppn_masukan

def get_condition(filters):
	conditions = ""

	if filters.get("company"):
		conditions += " AND pi.company = %(company)s"

	if filters.get("unit"):
		conditions += " AND pi.unit = %(unit)s"

	if filters.get("jenis_pajak"):
		conditions += " AND vd.type = %(jenis_pajak)s"

	if filters.get("from_date") and filters.get("to_date"):
		conditions += " AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("Nama Vendor"),
			"fieldtype": "Data",
			"fieldname": "nama_vendor",
		},
		{
			"label": _("Kode Akun"),
			"fieldtype": "Data",
			"fieldname": "kode_akun",
		},
		{
			"label": _("DPP"),
			"fieldtype": "Currency",
			"fieldname": "dpp",
		},
		{
			"label": _("PPH"),
			"fieldtype": "Currency",
			"fieldname": "pph",
		},
		{
			"label": _("PPN"),
			"fieldtype": "Currency",
			"fieldname": "ppn",
		},
		{
			"label": _("No Invoice"),
			"fieldtype": "Data",
			"fieldname": "no_invoice",
		},
		{
			"label": _("No Faktur"),
			"fieldtype": "Data",
			"fieldname": "no_faktur",
		},
		{
			"label": _("No Faktur Pengganti"),
			"fieldtype": "Data",
			"fieldname": "no_faktur_pengganti",
		},
		{
			"label": _("Tanggal Invoice"),
			"fieldtype": "Date",
			"fieldname": "tanggal_invoice",
		},
		{
			"label": _("Jenis Pajak"),
			"fieldtype": "Data",
			"fieldname": "jenis_pajak",
		},
		{
			"label": _("Summary All PPH"),
			"fieldtype": "Currency",
			"fieldname": "summary_all_pph",
		},
	]

	return columns

def get_jenis_pajak(parent):
	query = frappe.db.sql("""
		SELECT vd.`type`
		FROM `tabVAT Detail` as vd
		WHERE vd.parent = %(parent)s
	""", {
		"parent": parent
	}, as_dict=True)

	return ", ".join([d["type"] for d in query if d.get("type")])