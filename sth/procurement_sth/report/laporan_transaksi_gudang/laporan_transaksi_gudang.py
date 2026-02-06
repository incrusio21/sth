# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	columns, data = get_columns(), get_data(filters)
	return columns, data

def get_columns():
	return [
		{
			'fieldname': 'tipe_transaksi',
			'label': _('Tipe Transaksi'),
			'fieldtype': 'Data',
			'width' : 150,
		},
		{
			'fieldname': 'tanggal',
			'label': _('Tanggal'),
			'fieldtype': 'Date',
			'width' : 150,
		},
		{
			'fieldname': 'kode_barang',
			'label': _('Kode Barang'),
			'fieldtype': 'Link',
			'options': 'Item',
			'width' : 150,
		},
		{
			'fieldname': 'nama_barang',
			'label': _('Nama Barang'),
			'fieldtype': 'Data',
			'width' : 200,
		},
		{
			'fieldname': 'kelompok_barang',
			'label': _('Kelompok Barang'),
			'fieldtype': 'Data',
			'width' : 200,
		},
		{
			'fieldname': 'sub_kelompok_barang',
			'label': _('Sub Kelompok Barang'),
			'fieldtype': 'Data',
			'width' : 200,
		},
		{
			'fieldname': 'satuan',
			'label': _('Satuan'),
			'fieldtype': 'Data',
			'width' : 150,
		},
		{
			'fieldname': 'masuk',
			'label': _('Masuk'),
			'fieldtype': 'Float',
			'width' : 150,
		},
		{
			'fieldname': 'keluar',
			'label': _('Keluar'),
			'fieldtype': 'Float',
			'width' : 150,
		},
		{
			'fieldname': 'saldo',
			'label': _('Saldo'),
			'fieldtype': 'Float',
			'width' : 150,
		},
		{
			'fieldname': 'tujuan',
			'label': _('Tujuan/Sumber'),
			'fieldtype': 'Link',
			'options': 'Warehouse',
			'width' : 200,
		},
		{
			'fieldname': 'kode_kegiatan',
			'label': _('Kode Kegiatan'),
			'fieldtype': 'Data',
			'width' : 200,
		},
		{
			'fieldname': 'no_transaksi',
			'label': _('No Transaksi'),
			'fieldtype': 'Data',
			'width' : 200,
		},
	]

def get_data(filters=None):
	where_clause = "where sle.is_cancelled = 0"
	args = {}
	if filters.company:
		where_clause += " AND sle.company = %(company)s"
		args["company"] = filters.company
	
	if filters.item_code:
		where_clause += " AND sle.item_code = %(item_code)s"
		args["item_code"] = filters.item_code

	query = frappe.db.sql(f"""
		SELECT "" as tipe_transaksi,sle.posting_date as tanggal, sle.item_code as kode_barang, i.item_name as nama_barang, i.kelompok_barang, 
		i.nama_sub_kelompok_barang as sub_kelompok_barang, i.stock_uom as satuan,
		CASE 
			WHEN sle.actual_qty > 0 THEN sle.actual_qty
			ELSE 0
		END as masuk,
		CASE 
			WHEN sle.actual_qty < 0 THEN ABS(sle.actual_qty)
			ELSE 0
		END as keluar,
		COALESCE(sle.qty_after_transaction,0) as saldo, sle.warehouse as tujuan,"" as kode_kegiatan, sle.voucher_no as no_transaksi
		FROM `tabStock Ledger Entry` sle
		JOIN `tabItem` i on i.name = sle.item_code
		{where_clause}
	""",args,as_dict=True)

	return query
