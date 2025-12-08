# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns(filters)
	data = []

	data.append({
		"kode_pt": "TPRM"
	})

	return columns, data

def get_columns(filters):
	columns = [
		{
			"label": _("Kode PT"),
			"fieldtype": "Data",
			"fieldname": "kode_pt",
			"width": 150
		},
		{
			"label": _("No Transaksi"),
			"fieldtype": "Data",
			"fieldname": "no_transaksi",
			"width": 150
		},
		{
			"label": _("Tanggal"),
			"fieldtype": "Date",
			"fieldname": "tanggal",
			"width": 150
		},
		{
			"label": _("No.Kontrak"),
			"fieldtype": "Data",
			"fieldname": "no_kontrak",
			"width": 150
		},
		{
			"label": _("No. SIPB"),
			"fieldtype": "Data",
			"fieldname": "no_sipb",
			"width": 150
		},
		{
			"label": _("No. DO"),
			"fieldtype": "Data",
			"fieldname": "no_do",
			"width": 150
		},
		{
			"label": _("Kendaraan"),
			"fieldtype": "Data",
			"fieldname": "kendaraan",
			"width": 150
		},
		{
			"label": _("Nama Sopir"),
			"fieldtype": "Data",
			"fieldname": "nama_sopir",
			"width": 150
		},
		{
			"label": _("Berat Bersih Pabrik"),
			"fieldtype": "Data",
			"fieldname": "berat_bersih_pabrik",
			"width": 150
		},
		{
			"label": _("Berat Bersih Pembeli"),
			"fieldtype": "Data",
			"fieldname": "berat_bersih_pembeli",
			"width": 150
		},
		{
			"label": _("Nama Customer Kontrak"),
			"fieldtype": "Data",
			"fieldname": "nama_customer_kontrak",
			"width": 150
		},
		{
			"label": _("Harga Satuan Kontrak"),
			"fieldtype": "Data",
			"fieldname": "harga_satuan_kontrak",
			"width": 150
		},
		{
			"label": _("Nilai per Truk Kontrak"),
			"fieldtype": "Data",
			"fieldname": "nilai_per_truk_kontrak",
			"width": 150
		},
		{
			"label": _("Nama Customer Transportir"),
			"fieldtype": "Data",
			"fieldname": "nama_customer_transportir",
			"width": 150
		},
		{
			"label": _("Harga Satuan Transportir"),
			"fieldtype": "Data",
			"fieldname": "harga_satuan_transportir",
			"width": 150
		},
		{
			"label": _("Nilai per Truk Transportir"),
			"fieldtype": "Data",
			"fieldname": "nilai_per_truk_transportir",
			"width": 150
		},
		{
			"label": _("No. Invoice"),
			"fieldtype": "Data",
			"fieldname": "no_invoice",
			"width": 150
		},
	]

	return columns