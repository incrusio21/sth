# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns(filters)
	data = []
	conditions = get_condition(filters)

	query_rkt = frappe.db.sql("""
	SELECT 
	btt.name,
	abdk.name AS kode_kendaraan,
	abdk.nama_alat,
	CASE 
			WHEN abdk.tipe_master = 'Kendaraan' THEN abdk.no_pol
			ELSE ''
	END AS no_identifikasi,
	btt.total_km_hm AS hm_km,
	btt.upah_amount AS upah_dan_premi,
	btt.bahan_bakar_amount AS bbm,
	btt.suku_cadang_amount AS suku_cadang,
	btt.biaya_servis_amount AS service,
	btt.biaya_umum_amount AS lain_lain,
	(
			COALESCE(btt.upah_amount, 0) +
			COALESCE(btt.bahan_bakar_amount, 0) +
			COALESCE(btt.suku_cadang_amount, 0) +
			COALESCE(btt.biaya_servis_amount, 0) +
			COALESCE(btt.biaya_umum_amount, 0)
	) AS total,
	(
			(
					COALESCE(btt.upah_amount, 0) +
					COALESCE(btt.bahan_bakar_amount, 0) +
					COALESCE(btt.suku_cadang_amount, 0) +
					COALESCE(btt.biaya_servis_amount, 0) +
					COALESCE(btt.biaya_umum_amount, 0)
			) / NULLIF(btt.total_km_hm, 0)
	) AS rp_sat
	FROM `tabBudget Traksi Tahunan` btt
	JOIN `tabAlat Berat Dan Kendaraan` abdk ON abdk.name = btt.kode_kendaraan
	WHERE btt.company IS NOT NULL {};
	""".format(conditions), filters, as_dict=True)

	for rkt in query_rkt:
		data.append({
			'kode_kendaraan': rkt['kode_kendaraan'],
			'nama_alat': rkt['nama_alat'],
			'no_identifikasi': rkt['no_identifikasi'],
			'hm_km': rkt['hm_km'],
			'upah_dan_premi': rkt['upah_dan_premi'],
			'bbm': rkt['bbm'],
			'suku_cadang': rkt['suku_cadang'],
			'service': rkt['service'],
			'lain_lain': rkt['lain_lain'],
			'total': rkt['total'],
			'rp_sat': rkt['rp_sat'],
		})

	return columns, data

def get_condition(filters):
	conditions = "AND btt.company = %(company)s"

	if filters.get("unit"):
		conditions += " AND btt.unit = %(unit)s"
	
	if filters.get("divisi"):
		conditions += " AND btt.divisi = %(divisi)s"
	
	if filters.get("kode_kendaraan"):
		conditions += " AND btt.kode_kendaraan = %(kode_kendaraan)s"
	
	if filters.get("periode"):
		conditions += " AND btt.thn_bgt = %(periode)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("Kode Kendaraan"),
			"fieldtype": "Data",
			"fieldname": "kode_kendaraan",
		},
		{
			"label": _("Nama Alat"),
			"fieldtype": "Data",
			"fieldname": "nama_alat"
		},
		{
			"label": _("No Identifikasi"),
			"fieldtype": "Data",
			"fieldname": "no_identifikasi"
		},
		{
			"label": _("HM/KM"),
			"fieldtype": "Data",
			"fieldname": "hm_km"
		},
		{
			"label": _("Upah dan Premi"),
			"fieldtype": "Currency",
			"fieldname": "upah_dan_premi",
			"width": 150
		},
		{
			"label": _("BBM"),
			"fieldtype": "Currency",
			"fieldname": "bbm",
			"width": 150
		},
		{
			"label": _("Suku Cadang"),
			"fieldtype": "Currency",
			"fieldname": "suku_cadang",
			"width": 150
		},
		{
			"label": _("Service"),
			"fieldtype": "Currency",
			"fieldname": "service",
			"width": 150
		},
		{
			"label": _("Lain-lain"),
			"fieldtype": "Currency",
			"fieldname": "lain_lain",
			"width": 150
		},
		{
			"label": _("Total"),
			"fieldtype": "Currency",
			"fieldname": "total",
			"width": 150
		},
		{
			"label": _("Rp/Sat"),
			"fieldtype": "Currency",
			"fieldname": "rp_sat",
			"width": 150
		}
	]

	return columns