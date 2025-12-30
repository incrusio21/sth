# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	query_l_deposito = frappe.db.sql("""
		SELECT 
		dit.posting_date as tgl_penempatan,
		DATE_FORMAT(dit.posting_date, '%b') as bulan,
		DATE_FORMAT(dit.posting_date, '%Y') as tahun,
		d.bank as nama_bank,
		d.deposito_type as jenis_deposito,
		d.currency as mata_uang,
		dit.deposito_amount as nilai_pokok,
		CONCAT(ROUND(dit.interest, 2), ' ', '%') as suku_bunga,
		CONCAT(d.tenor, ' ', 'bulan') as jangka_waktu,
		dit.maturity_date as tgl_jatuh_tempo,
		d.docstatus as status_deposito,
		d.interest_amount as bunga_bruto,
		d.tax_amount as pajak,
		d.total as bunga_neto,
		d.is_redeemed as dicairkan
		FROM `tabDeposito` as d
		JOIN `tabDeposito Interest Table` as dit ON dit.parent = d.name;
  """, as_dict=True)

	for deposito in query_l_deposito:
		data.append(deposito)

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("pt"):
		conditions += " AND et.company = %(pt)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("Tanggal Penempatan"),
			"fieldtype": "Date",
			"fieldname": "tgl_penempatan",
		},
		{
			"label": _("Bulan"),
			"fieldtype": "Data",
			"fieldname": "bulan",
		},
		{
			"label": _("Tahun"),
			"fieldtype": "Data",
			"fieldname": "tahun",
		},
		{
			"label": _("Nama Bank"),
			"fieldtype": "Data",
			"fieldname": "nama_bank",
		},
		{
			"label": _("Jenis Deposito"),
			"fieldtype": "Data",
			"fieldname": "jenis_deposito",
		},
		{
			"label": _("Mata Uang"),
			"fieldtype": "Data",
			"fieldname": "mata_uang",
		},
		{
			"label": _("Nilai Pokok"),
			"fieldtype": "Currency",
			"fieldname": "nilai_pokok",
		},
		{
			"label": _("Suku Bunga"),
			"fieldtype": "Data",
			"fieldname": "suku_bunga",
		},
		{
			"label": _("Jangka Waktu"),
			"fieldtype": "Data",
			"fieldname": "jangka_waktu",
		},
		{
			"label": _("Tanggal Jatuh Tempo"),
			"fieldtype": "Date",
			"fieldname": "tgl_jatuh_tempo",
		},
		{
			"label": _("Status Deposito"),
			"fieldtype": "Data",
			"fieldname": "status_deposito",
		},
		{
			"label": _("Bunga Bruto"),
			"fieldtype": "Currency",
			"fieldname": "bunga_bruto",
		},
		{
			"label": _("Pajak"),
			"fieldtype": "Currency",
			"fieldname": "pajak",
		},
		{
			"label": _("Bunga Neto"),
			"fieldtype": "Currency",
			"fieldname": "bunga_neto",
		},
		{
			"label": _("Dicairkan?"),
			"fieldtype": "Data",
			"fieldname": "dicairkan",
		},
	]

	return columns