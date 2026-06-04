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
		MAX(sle.fiscal_year) as periode,
		sle.warehouse as warehouse,
		sle.item_code as kode_barang,
		i.item_name as nama_barang,
		i.kode_kelompok_barang as kode_kelompok_barang,
		ig_kelompok.item_group_name as kelompok_barang,
		i.kode_sub_kelompok_barang as kode_sub_kelompok_barang,
		ig_sub_kelompok.item_group_name as sub_kelompok_barang,
		"" as tanggal_terakhir_po,
  	SUM(sle.actual_qty) as jumlah_qty,
		DATEDIFF(%(to_date)s, MAX(sle.posting_date)) as jumlah_hari,
		SUM(sle.stock_value_difference) as total
		FROM `tabStock Ledger Entry` as sle
		LEFT JOIN `tabItem` as i ON i.name = sle.item_code
		LEFT JOIN `tabItem Group` as ig_kelompok ON ig_kelompok.name = i.kode_kelompok_barang
		LEFT JOIN `tabItem Group` as ig_sub_kelompok ON ig_sub_kelompok.name = i.kode_sub_kelompok_barang
  	WHERE sle.posting_date <= %(to_date)s
		AND sle.is_cancelled = 0
		{conditions}
		GROUP BY sle.item_code, sle.warehouse;
  """, {
		"to_date": filters.get("to_date"),
		"company": filters.get("company"),
		"gudang": filters.get("gudang"),
		"item_group": filters.get("item_group"),
		"item_code": filters.get("item_code")
  }, as_dict=True)
 
	for row in query :
		row["tanggal_terakhir_po"] = get_latest_date_po(row.get("kode_barang")).get("transaction_date")
		data.append(row)

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("company"):
		conditions += " AND sle.company = %(company)s"

	if filters.get("gudang"):
		conditions += " AND sle.warehouse = %(gudang)s"

	if filters.get("item_group"):
		conditions += " AND i.kelompok_barang = %(item_group)s"

	if filters.get("item_code"):
		conditions += " AND i.item_code = %(item_code)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("Periode"),
			"fieldtype": "Data",
			"fieldname": "periode",
		},
		{
			"label": _("Warehouse"),
			"fieldtype": "Data",
			"fieldname": "warehouse",
		},
		{
			"label": _("Kode Barang"),
			"fieldtype": "Data",
			"fieldname": "kode_barang",
		},
		{
			"label": _("Nama Barang"),
			"fieldtype": "Data",
			"fieldname": "nama_barang",
		},
		{
			"label": _("Kode Kelompok Barang"),
			"fieldtype": "Data",
			"fieldname": "kode_kelompok_barang",
		},
		{
			"label": _("Kelompok Barang"),
			"fieldtype": "Data",
			"fieldname": "kelompok_barang",
		},
		{
			"label": _("Kode Sub Kelompok Barang"),
			"fieldtype": "Data",
			"fieldname": "kode_sub_kelompok_barang",
		},
		{
			"label": _("Sub Kelompok Barang"),
			"fieldtype": "Data",
			"fieldname": "sub_kelompok_barang",
		},
		{
			"label": _("Tanggal Terakhir PO"),
			"fieldtype": "Date",
			"fieldname": "tanggal_terakhir_po",
		},
		{
			"label": _("Jumlah QTY"),
			"fieldtype": "Data",
			"fieldname": "jumlah_qty",
		},
		{
			"label": _("Jumlah Hari"),
			"fieldtype": "Data",
			"fieldname": "jumlah_hari",
		},
		{
			"label": _("Total"),
			"fieldtype": "Data",
			"fieldname": "total",
		},
	]

	return columns

def get_latest_date_po(item_code):
  query = frappe.db.sql("""
		SELECT
			poi.parent,
			po.status,
			po.transaction_date
		FROM `tabPurchase Order Item` as poi
		LEFT JOIN `tabPurchase Order` as po 
			ON po.name = poi.parent
		WHERE 
			po.status = 'Completed'
			AND poi.item_code = %(item_code)s
		ORDER BY po.transaction_date DESC
		LIMIT 1;
  """, {
		"item_code": item_code
  }, as_dict=True)
  
  return query[0] if query else {}