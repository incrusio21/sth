# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	# query = frappe.db.sql(f"""
	# 	SELECT 
	# 	t.ticket_number as no_tiket,
	# 	do.sales_order as no_kontrak,
	# 	so.no_kontrak_external as no_kontrak_external,
	# 	t.do_no as no_do,
	# 	t.nama_barang as produk,
	# 	t.driver_name as supir,
	# 	t.no_polisi as no_pol,
	# 	s.supplier_name as transportir,
	# 	t.posting_date as tanggal,
	# 	t.weight_in_time as jam_masuk,
	# 	t.weight_out_time as jam_keluar,
	# 	t.tara as first_weight,
	# 	t.bruto as second_weight,
	# 	t.netto as netto
	# 	FROM `tabTimbangan` as t
	# 	LEFT JOIN `tabDelivery Order` as do ON do.name = t.do_no
	# 	LEFT JOIN `tabSales Order` as so ON so.name = do.sales_order
	# 	LEFT JOIN `tabSupplier` as s ON s.kode_supplier = t.transportir
	# 	WHERE t.docstatus = 1 AND t.`type` = 'Dispatch' {conditions}
	# 	ORDER BY t.nama_barang, t.posting_date;
	# """, filters, as_dict=True)
	query = frappe.db.sql(f"""
		SELECT
			t.ticket_number AS no_tiket,
			do.sales_order AS no_kontrak,
			so.no_kontrak_external AS no_kontrak_external,
			t.do_no AS no_do,
			t.nama_barang AS produk,
			t.driver_name AS supir,
			t.no_polisi AS no_pol,
			s.supplier_name AS transportir,
			t.posting_date AS tanggal,
			t.weight_in_time AS jam_masuk,
			t.weight_out_time AS jam_keluar,
			t.tara * (t.qty_do/t.netto) AS first_weight,
			t.bruto * (t.qty_do/t.netto) AS second_weight,
			t.qty_do AS netto
		FROM `tabTimbangan` AS t
		LEFT JOIN `tabDelivery Order` AS do
			ON do.name = t.do_no
		LEFT JOIN `tabSales Order` AS so
			ON so.name = do.sales_order
		LEFT JOIN `tabSupplier` AS s
			ON s.kode_supplier = t.transportir
		WHERE
			t.docstatus = 1
			AND t.`type` = 'Dispatch'
			AND t.name = 'TBG-20775'
			{conditions}

		UNION ALL

		SELECT
			t.ticket_number AS no_tiket,
			do2.sales_order AS no_kontrak,
			so2.no_kontrak_external AS no_kontrak_external,
			t.no_do_2 AS no_do,
			t.nama_barang AS produk,
			t.driver_name AS supir,
			t.no_polisi AS no_pol,
			s.supplier_name AS transportir,
			t.posting_date AS tanggal,
			t.weight_in_time AS jam_masuk,
			t.weight_out_time AS jam_keluar,
			t.tara * (t.qty_do_2/t.netto) AS first_weight,
			t.bruto * (t.qty_do_2/t.netto) AS second_weight,
			t.qty_do_2 AS netto
		FROM `tabTimbangan` AS t
		LEFT JOIN `tabDelivery Order` AS do2
			ON do2.name = t.no_do_2
		LEFT JOIN `tabSales Order` AS so2
			ON so2.name = do2.sales_order
		LEFT JOIN `tabSupplier` AS s
			ON s.kode_supplier = t.transportir
		WHERE
			t.docstatus = 1
			AND t.`type` = 'Dispatch'
			AND t.name = 'TBG-20775'
			AND t.no_do_2 IS NOT NULL
			AND t.no_do_2 != ''
			{conditions}

		ORDER BY produk, tanggal;
	""", filters, as_dict=True)

	current_produk = None

	subtotal_first = 0
	subtotal_second = 0
	subtotal_netto = 0

	for row in query:
		if current_produk and current_produk != row.produk:
			data.append({
				"jam_keluar": "<b>SubTotal</b>",
				"first_weight": fmt_number(subtotal_first, bold=True),
				"second_weight": fmt_number(subtotal_second, bold=True),
				"netto": fmt_number(subtotal_netto, bold=True),
				"is_subtotal": 1
			})

			subtotal_first = 0
			subtotal_second = 0
			subtotal_netto = 0

		current_produk = row.produk

		subtotal_first += row.first_weight or 0
		subtotal_second += row.second_weight or 0
		subtotal_netto += row.netto or 0

		# format angka baris normal (non-bold) supaya konsisten dengan baris subtotal
		row.first_weight = fmt_number(row.first_weight)
		row.second_weight = fmt_number(row.second_weight)
		row.netto = fmt_number(row.netto)

		data.append(row)

	if current_produk:
		data.append({
			"jam_keluar": "<b>SubTotal</b>",
			"first_weight": fmt_number(subtotal_first, bold=True),
			"second_weight": fmt_number(subtotal_second, bold=True),
			"netto": fmt_number(subtotal_netto, bold=True),
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
		conditions += " AND t.nama_barang LIKE %(produk)s"
		filters["produk"] = f"%{filters.get('produk')}%"

	if filters.get("transportir"):
		conditions += " AND s.supplier_name LIKE %(transportir)s"
		filters["transportir"] = f"%{filters.get('transportir')}%"

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
			"label": _("No.Kontrak External"),
			"fieldtype": "Data",
			"fieldname": "no_kontrak_external",
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
			"width": 200
		},
		{
			"label": _("Supir"),
			"fieldtype": "Data",
			"fieldname": "supir",
			"width": 200
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
			"fieldtype": "Data",
			"fieldname": "first_weight",
			"align": "right",
			"width": 150
		},
		{
			"label": _("2st Weight"),
			"fieldtype": "Data",
			"fieldname": "second_weight",
			"align": "right",
			"width": 150
		},
		{
			"label": _("Netto"),
			"fieldtype": "Data",
			"fieldname": "netto",
			"align": "right",
			"width": 150
		},
	]

	return columns

def fmt_number(value, bold=False):
	"""Format angka dengan pemisah ribuan ala Indonesia (titik ribuan, koma desimal)."""
	formatted = "{:,.2f}".format(value or 0).replace(",", "X").replace(".", ",").replace("X", ".")
	if bold:
		formatted = f"<b>{formatted}</b>"
	return formatted