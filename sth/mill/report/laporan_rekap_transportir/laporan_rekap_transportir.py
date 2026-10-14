# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data

def get_columns(filters):
	columns = [
		{
			"label": _("Tanggal"),
			"fieldname": "tanggal",
			"fieldtype": "Date",
		},
		{
			"label": _("Pabrik"),
			"fieldname": "pabrik",
			"fieldtype": "Link",
			"options": "Unit"
		},
		{
			"label": _("Nomor Kontrak"),
			"fieldname": "nomor_kontrak",
			"fieldtype": "Link",
			"options": "Sales Order"
		},
		{
			"label": _("No. DO"),
			"fieldname": "nomor_do",
			"fieldtype": "Link",
			"options": "Delivery Order"
		},
		{
			"label": _("Nopol"),
			"fieldname": "nopol",
			"fieldtype": "Data"
		},
		{
			"label": _("Nama Supir"),
			"fieldname": "nama_supir",
			"fieldtype": "Data"
		},
		{
			"label": _("Transportir"),
			"fieldname": "transportir",
			"fieldtype": "Data"
		},
		{
			"label": _("Produk"),
			"fieldname": "produk",
			"fieldtype": "Data"
		},
		{
			"label": _("Qty-Netto"),
			"fieldname": "qty_netto",
			"fieldtype": "Float"
		},
		{
			"label": _("Harga/KG"),
			"fieldname": "harga_per_kg",
			"fieldtype": "Currency"
		},
		{
			"label": _("Harga"),
			"fieldname": "harga",
			"fieldtype": "Currency"
		},
		{
			"label": _("Qty Trans"),
			"fieldname": "qty_trans",
			"fieldtype": "Float"
		},
		{
			"label": _("Harga/KG Trans"),
			"fieldname": "harga_per_kg_trans",
			"fieldtype": "Currency"
		},
		{
			"label": _("Total Trans"),
			"fieldname": "total_trans",
			"fieldtype": "Currency"
		},
	]
 
	return columns

def get_data(filters):
	conditions = get_condition(filters)
	data = []
 
	query = frappe.db.sql(f"""
		SELECT 
		t.posting_date as tanggal,
		t.unit as pabrik,
		do.sales_order as nomor_kontrak,
		do.name as nomor_do,
		t.no_polisi as nopol,
		t.driver_name as nama_supir,
		s.supplier_name as transportir,
		t.nama_barang as produk,
		t.netto as qty_netto,
		doi.rate as harga_per_kg,
		(t.netto * doi.rate) as harga,
		sii.qty_timbang_customer as qty_trans,
		do.ongkos_angkut as harga_per_kg_trans,
		(sii.qty_timbang_customer * do.ongkos_angkut) as total_trans
		FROM `tabTimbangan` as t
		LEFT JOIN `tabDelivery Order` as do ON do.name = t.do_no
		LEFT JOIN `tabDelivery Order Item` as doi ON doi.parent = do.name
		LEFT JOIN `tabSales Invoice Item` as sii ON sii.parent = t.sales_invoice
		LEFT JOIN `tabSupplier` as s ON s.name = t.transportir
  	WHERE t.docstatus = 1 {conditions};
  """, filters, as_dict=True)
 
	for row in query:
		data.append(row)

	return data

def get_condition(filters):
	conditions = ""

	if filters.get("company"):
		conditions += " AND t.company = %(company)s"

	if filters.get("unit"):
		conditions += " AND t.unit = %(unit)s"

	if filters.get("no_kontrak"):
		conditions += " AND do.sales_order = %(no_kontrak)s"

	if filters.get("no_do"):
		conditions += " AND do.name = %(no_do)s"

	if filters.get("no_polisi"):
		conditions += " AND t.no_polisi = %(no_polisi)s"

	if filters.get("transportir"):
		conditions += " AND t.transportir = %(transportir)s"

	if filters.get("produk"):
		conditions += " AND t.kode_barang = %(produk)s"

	if filters.get("from_date") and filters.get("to_date"):
		conditions += " AND t.posting_date BETWEEN %(from_date)s AND %(to_date)s"

	return conditions