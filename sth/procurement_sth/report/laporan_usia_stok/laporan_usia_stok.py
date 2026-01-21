# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import frappe
from frappe import _
from frappe.utils import cint

def execute(filters):
	columns = get_columns()
	data = get_data(filters)

	return columns, data

def get_columns():
	return [
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
			'label': _('Kel Barang'),
			'fieldtype': 'Link',
			'options': 'Item Group',
			'width' : 150,
		},
		{
			'fieldname': 'sub_kelompok_barang',
			'label': _('Sub Kel Barang'),
			'fieldtype': 'Link',
			'options': 'Item Group',
			'width' : 150,
		},
		{
			'fieldname': 'satuan',
			'label': _('Satuan'),
			'fieldtype': 'Link',
			'options': 'UOM',
			'width' : 100,
		},
		{
			'fieldname': 'tanggal_po',
			'label': _('Tgl. Terakhir PO'),
			'fieldtype': 'Link',
			'options': 'Item',
			'width' : 150,
		},
		{
			'fieldname': 'qty',
			'label': _('Jumlah Qty'),
			'fieldtype': 'Float',
			'width' : 150,
		},
		{
			'fieldname': 'hari',
			'label': _('Jumlah Hari'),
			'fieldtype': 'Int',
			'width' : 150,
		},
		{
			'fieldname': 'total',
			'label': _('Total'),
			'fieldtype': 'Float',
			'width' : 150,
		},
	]

def get_data(filters):
	params = {
		"company": filters.company,
		"from_date": filters.from_date,
		"to_date": filters.to_date
	}

	subquery_conditions = ""
	additional_conditions = "WHERE 1=1"

	if filters.warehouse:
		subquery_conditions += " AND sle.warehouse = %(warehouse)s"
		params["warehouse"] = filters.warehouse

	if filters.kelompok_barang:
		additional_conditions += " AND i.kelompok_barang = %(kelompok_barang)s"
		params["kelompok_barang"] = filters.kelompok_barang

	if filters.kelompok_barang:
		additional_conditions += " AND i.item_group = %(sub_kelompok_barang)s"
		params["sub_kelompok_barang"] = filters.sub_kelompok_barang
	
	if filters.nama_barang:
		additional_conditions += " AND i.item_name LIKE %(nama_barang)s"
		params["nama_barang"] = f"%{filters.nama_barang}%"

	query = frappe.db.sql(f"""
		select i.item_code as kode_barang, i.item_name as nama_barang,i.kelompok_barang , i.item_group as sub_kelompok_barang, i.stock_uom as satuan,
		COALESCE(sl.qty_after_transaction,0) as qty, "" as hari,pri.purchase_order,po.transaction_date as tanggal_po, "" as "total"
		from `tabItem` i
		join(
			SELECT item_code, warehouse, MAX(posting_datetime), sle.valuation_rate, sle.is_cancelled, sle.qty_after_transaction,
			sle.voucher_type ,sle.voucher_no, sle.company 
			FROM `tabStock Ledger Entry` sle
			where sle.is_cancelled = 0 and sle.posting_date BETWEEN %(from_date)s and %(to_date)s  
			and sle.company = %(company)s {subquery_conditions}
			GROUP BY item_code
		) sl on sl.item_code = i.name
		left JOIN `tabPurchase Receipt Item` pri on pri.parent = sl.voucher_no and pri.item_code = i.item_code 
		left join `tabPurchase Order` po on po.name = pri.purchase_order
		{additional_conditions}
	""",params,as_dict=True)

	total = 0
	for row in query:
		row.total = cint(row.qty) + total
		total = row.total


	return query