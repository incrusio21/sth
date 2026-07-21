# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	query = frappe.db.sql(f"""
		SELECT 
		t.ticket_number as no_tiket,
		do.sales_order as no_kontrak,
		t.do_no as no_do,
		t.nama_barang as produk,
		t.driver_name as supir,
		t.no_polisi as no_pol,
		t.transportir as transportir,
		t.posting_date as tanggal,
		t.weight_in_time as jam_masuk,
		t.weight_out_time as jam_keluar,
		t.tara as 1st_weight,
		t.bruto as 2st_weight,
		t.netto as netto
		FROM `tabTimbangan` as t
		LEFT JOIN `tabDelivery Order` as do ON do.name = t.do_no
		WHERE t.docstatus = 1 AND t.`type` = 'Dispatch' {conditions};
	""", filters, as_dict=True)

	current_produk = None

	subtotal_first = 0
	subtotal_second = 0
	subtotal_netto = 0

	for row in query:
		if current_produk and current_produk != row.produk:
			data.append({
				"jam_keluar": "<b>SubTotal</b>",
				"first_weight": subtotal_first,
				"second_weight": subtotal_second,
				"netto": subtotal_netto,
				"is_subtotal": 1
			})

			subtotal_first = 0
			subtotal_second = 0
			subtotal_netto = 0

		current_produk = row.produk

		subtotal_first += row.first_weight or 0
		subtotal_second += row.second_weight or 0
		subtotal_netto += row.netto or 0

		data.append(row)

	if current_produk:
		data.append({
			"jam_keluar": "<b>SubTotal</b>",
			"first_weight": subtotal_first,
			"second_weight": subtotal_second,
			"netto": subtotal_netto,
			"is_subtotal": 1
		})

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("company"):
		conditions += " AND t.company = %(company)s"

	if filters.get("unit"):
		conditions += " AND t.unit = %(unit)s"

	if filters.get("no_kontrak"):
		conditions += " AND do.sales_order = %(no_kontrak)s"

	if filters.get("no_do"):
		conditions += " AND t.do_no = %(no_do)s"

	if filters.get("produk"):
		conditions += " AND t.nama_barang = %(produk)s"

	if filters.get("transportir"):
		conditions += " AND t.transportir = %(transportir)s"

	if filters.get("from_date") and filters.get("to_date"):
		conditions += " AND t.posting_date BETWEEN %(from_date)s AND %(to_date)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("No.Tiket"),
			"fieldtype": "Data",
			"fieldname": "no_tiket",
		},
		{
			"label": _("No.Kontrak"),
			"fieldtype": "Data",
			"fieldname": "no_kontrak",
		},
		{
			"label": _("No.DO"),
			"fieldtype": "Data",
			"fieldname": "no_do",
		},
		{
			"label": _("Produk"),
			"fieldtype": "Data",
			"fieldname": "produk",
		},
		{
			"label": _("Supir"),
			"fieldtype": "Data",
			"fieldname": "supir",
		},
		{
			"label": _("NOPOL"),
			"fieldtype": "Data",
			"fieldname": "no_pol",
		},
		{
			"label": _("Transportir"),
			"fieldtype": "Data",
			"fieldname": "transportir",
		},
		{
			"label": _("Tanggal"),
			"fieldtype": "Date",
			"fieldname": "tanggal",
		},
		{
			"label": _("Jam Masuk"),
			"fieldtype": "Data",
			"fieldname": "jam_masuk",
		},
		{
			"label": _("Jam Keluar"),
			"fieldtype": "Data",
			"fieldname": "jam_keluar",
		},
		{
			"label": _("1st Weight"),
			"fieldtype": "Float",
			"fieldname": "first_weight",
		},
		{
			"label": _("2st Weight"),
			"fieldtype": "Float",
			"fieldname": "second_weight",
		},
		{
			"label": _("Netto"),
			"fieldtype": "Float",
			"fieldname": "netto",
		},
	]

	return columns