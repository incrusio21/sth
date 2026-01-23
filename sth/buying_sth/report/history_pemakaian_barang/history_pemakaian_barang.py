# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate
def execute(filters):
	months = [
		"Januari", "Februari", "Maret", "April", "Mei", "Juni",
		"Juli", "Agustus", "September", "Oktober", "November", "Desember"
	]

	columns, data = get_columns(filters,months), get_data(filters,months)
	return columns, data

def get_columns(filters,months):
	

	from_month = months.index(filters.from_month)
	to_month = months.index(filters.to_month)

	month_columns = []
	for d in range(from_month,to_month+1):
		month_columns.append({
			'fieldname': months[d],
			'label': _(f'{filters.year}-{str(d+1).zfill(2)}'),
			'fieldtype': 'Float',
			'width' : 150,
			"align": "left",
		})

	columns = [
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
			'width' : 150,
		},
		*month_columns,	
		{
			'fieldname': 'jumlah',
			'label': _('Jumlah'),
			'fieldtype': 'Float',
			'width' : 150,
		},
		{
			'fieldname': 'harga',
			'label': _('Harga'),
			'fieldtype': 'Currency',
			'width' : 150,
		},
		{
			'fieldname': 'total',
			'label': _('Total'),
			'fieldtype': 'Currency',
			'options': 'Item',
			'width' : 150,
		},
	]

	return columns

def get_data(filters,months):
	args = {
		"year": filters.year,
		"from_month":  months.index(filters.from_month) + 1,
		"to_month":  months.index(filters.to_month) + 1
	}

	query = frappe.db.sql("""
		SELECT pbi.`kode_barang`, i.`item_name` AS nama_barang, MONTH(pb.`tanggal`) AS bulan,
		SUM(pbi.`jumlah`) AS jumlah 
		FROM `tabPengeluaran Barang Item` pbi
		JOIN `tabPengeluaran Barang` pb ON pb.`name` = pbi.`parent`
		LEFT JOIN `tabAlat Berat Dan Kendaraan` k ON pbi.`kendaraan` = k.`name`
		JOIN `tabItem` i ON i.`name` = pbi.`kode_barang`
		WHERE pbi.`docstatus` = 1 AND YEAR(pb.`tanggal`) = %(year)s AND MONTH(pb.`tanggal`) BETWEEN %(from_month)s AND %(to_month)s
		GROUP BY pbi.`kode_barang`, MONTH(pb.`tanggal`)
		ORDER BY pb.`tanggal` ASC 
	""",args,as_dict=True,debug=True)

	result = []

	for data in query:
		dict_data = frappe._dict({})
		exists = next((r for r in result if r.kode_barang == data.kode_barang),None)

		if exists:
			exists[months[data.bulan-1]] = data.jumlah
			exists.jumlah += data.jumlah
		else:
			dict_data.kode_barang = data.kode_barang
			dict_data.nama_barang = data.nama_barang
			dict_data[months[data.bulan-1]] = data.jumlah
			dict_data.jumlah = data.jumlah
			result.append(dict_data)

	return result
