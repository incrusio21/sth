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
			"label": _("Tiket No"),
			"fieldname": "ticket_no",
			"fieldtype": "Link",
			"options": "Security Check Point"
		},
		{
			"label": _("SPB No."),
			"fieldname": "spb_no",
			"fieldtype": "Link",
			"options": "Surat Pengantar Buah"
		},
		{
			"label": _("Kontrak"),
			"fieldname": "kontrak",
			"fieldtype": "Link",
			"options": "Sales Order"
		},
		{
			"label": _("Pelanggan"),
			"fieldname": "pelanggan",
			"fieldtype": "Link",
			"options": "Customer"
		},
		{
			"label": _("No. Polisi"),
			"fieldname": "no_polisi",
			"fieldtype": "Data"
		},
		{
			"label": _("Supir"),
			"fieldname": "supir",
			"fieldtype": "Data"
		},
		{
			"label": _("Internal Berat Masuk"),
			"fieldname": "internal_berat_masuk",
			"fieldtype": "Float"
		},
		{
			"label": _("Internal Berat Keluar"),
			"fieldname": "internal_berat_keluar",
			"fieldtype": "Float"
		},
		{
			"label": _("Internal Berat Bersih"),
			"fieldname": "internal_berat_bersih",
			"fieldtype": "Float"
		},
		{
			"label": _("Internal Janjang"),
			"fieldname": "internal_janjang",
			"fieldtype": "Float"
		},
		{
			"label": _("External Berat Masuk"),
			"fieldname": "external_berat_masuk",
			"fieldtype": "Float"
		},
		{
			"label": _("External Berat Keluar"),
			"fieldname": "external_berat_keluar",
			"fieldtype": "Float"
		},
		{
			"label": _("External Berat Bersih"),
			"fieldname": "external_berat_bersih",
			"fieldtype": "Float"
		},
		{
			"label": _("External Potongan"),
			"fieldname": "external_potongan",
			"fieldtype": "Float"
		},
		{
			"label": _("External Berat Normal"),
			"fieldname": "external_berat_normal",
			"fieldtype": "Float"
		},
		{
			"label": _("Berat Pengakuan Jual"),
			"fieldname": "berat_pengakuan_jual",
			"fieldtype": "Float"
		},
		{
			"label": _("Varian Kg"),
			"fieldname": "varian_kg",
			"fieldtype": "Float"
		},
		{
			"label": _("Varian %"),
			"fieldname": "varian_percent",
			"fieldtype": "Percent"
		},
		{
			"label": _("Transportir"),
			"fieldname": "transportir",
			"fieldtype": "Data"
		},
		{
			"label": _("Denda Kg"),
			"fieldname": "denda_kg",
			"fieldtype": "Float"
		},
		{
			"label": _("Denda Harga TBS (Rp/Kg)"),
			"fieldname": "denda_harga_tbs",
			"fieldtype": "Float"
		},
		{
			"label": _("Denda Total Denda (Rp)"),
			"fieldname": "denda_total_denda",
			"fieldtype": "Currency"
		},
		{
			"label": _("Keterangan"),
			"fieldname": "keterangan",
			"fieldtype": "Data"
		},
	]
 
	return columns

def get_data(filters):
	data = []
 
	query = frappe.db.sql("""
		SELECT 
		t.posting_date as tanggal,
		t.ticket_number as ticket_no,
		t.spb as spb_no,
		do.sales_order as kontrak,
		do.customer as pelanggan,
		t.no_polisi as no_polisi,
		t.driver_name as supir,

		t.tara as internal_berat_masuk,
		t.bruto as internal_berat_keluar,
		t.netto as internal_berat_bersih,
		"" as internal_janjang,

		t.bruto_eksternal as external_berat_masuk,
		t.tara_eksternal as external_berat_keluar,
		t.netto_eksternal as external_berat_bersih,
		(t.sortasi_eksternal * t.netto_eksternal) as external_potongan,
		(t.netto_eksternal - t.sortasi_eksternal) as external_berat_normal,

		(t.netto_eksternal - t.sortasi_eksternal) as berat_pengakuan_jual,

		(t.netto - t.netto_eksternal) as varian_kg,
		(((t.netto - t.netto_eksternal) / t.netto) * 100) as varian_percent,

		t.transportir as transportir,

		((t.netto - t.netto_eksternal) - (t.netto * (3/100))) as denda_kg,
		doi.rate as denda_harga_tbs,
		((t.netto - t.netto_eksternal) - (t.netto * (3/100))) * 2 * doi.rate as denda_total_denda,

		CASE
				WHEN (((t.netto - t.netto_eksternal) / NULLIF(t.netto, 0)) * 100) >= 3
				THEN 'Melebihi toleransi 3%'
				ELSE ''
		END AS keterangan

		FROM `tabTimbangan` as t
		LEFT JOIN `tabDelivery Order` as do ON do.name = t.do_no
		LEFT JOIN `tabDelivery Order Item` as doi ON doi.parent = do.name
		WHERE t.company = 'PT. ALAO KUNING' AND (((t.netto - t.netto_eksternal) / NULLIF(t.netto, 0)) * 100) >= 3;
  """, as_dict=True)
 
	for row in query:
		data.append(row)

	return data