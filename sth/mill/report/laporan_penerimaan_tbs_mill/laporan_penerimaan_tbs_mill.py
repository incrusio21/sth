# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

from frappe import _
import frappe
from collections import defaultdict
from frappe.utils import flt

def execute(filters=None):
	laporan_type = filters.get("tbs", "External")
	columns = get_columns()
	data = []
	
	if laporan_type == "External":
		for row in get_data_external(filters):
			data.append({
				"is_group": 1,
				"no_polisi": row["grouping"]
			})

			for child in row["data"]:
				child["is_group"] = 0
				data.append(child)

			data.append({
				"is_group": 1,
				"jam_keluar": "Total",
				"bruto": round(sum(flt(d["bruto"] or 0) for d in row["data"]), 0),
				"tara": round(sum(flt(d["tara"] or 0) for d in row["data"]), 0),
				"netto_1": round(sum(flt(d["netto_1"] or 0) for d in row["data"]), 0),
				"sort": round(sum(flt(d["sort"] or 0) for d in row["data"]), 0),
				"netto_2": round(sum(flt(d["netto_2"] or 0) for d in row["data"]), 0),
				"bjr": round(sum(flt(d["bjr"] or 0) for d in row["data"]), 0),
				"grader": round(sum(flt(d["grader"] or 0) for d in row["data"]), 0),
			})
	else:
		for row in get_data_internal(filters):
			data.append({
				"is_group": 1,
				"no_polisi": row["grouping"]
			})

			for child in row["data"]:
				child["is_group"] = 0
				data.append(child)

			data.append({
				"is_group": 1,
				"jam_keluar": "Total",
				"bruto": round(sum(flt(d["bruto"] or 0) for d in row["data"]), 0),
				"tara": round(sum(flt(d["tara"] or 0) for d in row["data"]), 0),
				"netto_1": round(sum(flt(d["netto_1"] or 0) for d in row["data"]), 0),
				"sort": round(sum(flt(d["sort"] or 0) for d in row["data"]), 0),
				"netto_2": round(sum(flt(d["netto_2"] or 0) for d in row["data"]), 0),
				"bjr": round(sum(flt(d["bjr"] or 0) for d in row["data"]), 0),
				"grader": round(sum(flt(d["grader"] or 0) for d in row["data"]), 0),
			})
 
	return columns, data

def get_columns():
	"""Define kolom-kolom untuk laporan penerimaan TBS External"""
	return [
		{
			"fieldname": "no_polisi",
			"label": _("No. Polisi"),
			"fieldtype": "Data",
			"width": 100
		},
		{
			"fieldname": "no_referensi",
			"label": _("No. Referensi"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "no_slip_timbang",
			"label": _("No. Slip Timbang"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "nama_supir",
			"label": _("Nama Supir"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "tgl_masuk",
			"label": _("Tanggal Masuk"),
			"fieldtype": "Date",
			"width": 150
		},
		{
			"fieldname": "jam_masuk",
			"label": _("Jam Masuk"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "tgl_keluar",
			"label": _("Tanggal Keluar"),
			"fieldtype": "Date",
			"width": 150
		},
		{
			"fieldname": "jam_keluar",
			"label": _("Jam Keluar"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "bruto",
			"label": _("Bruto (Kg)"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "tara",
			"label": _("Tara (Kg)"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "netto_1",
			"label": _("Netto I (Kg)"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "sort",
			"label": _("Sort (Kg)"),
			"fieldtype": "Data",
			"width": 150
		},
  	{
			"fieldname": "netto_2",
			"label": _("Netto II (Kg)"),
			"fieldtype": "Data",
			"width": 150
		},
  	{
			"fieldname": "bjr",
			"label": _("BJR"),
			"fieldtype": "Data",
			"width": 150
		},
  	{
			"fieldname": "grader",
			"label": _("Grader"),
			"fieldtype": "Data",
			"width": 150
		},
	]

def get_condition(filters):
	conditions = ""
	laporan_type = filters.get("tbs", "External")

	if filters.get("supplier") and laporan_type == "External":
		conditions += " AND t.supplier = %(supplier)s"
	
	if filters.get("divisi") and laporan_type == "Internal":
		conditions += " AND spb.divisi = %(divisi)s"

	if filters.get("tanggal_dari") and filters.get("tanggal_sampai"):
		conditions += " AND t.posting_date BETWEEN %(tanggal_dari)s AND %(tanggal_sampai)s"

	if filters.get("unit"):
		conditions += " AND t.unit = %(unit)s"

	if filters.get("company"):
		conditions += " AND t.company = %(company)s"

	return conditions

def get_data_external(filters):
	conditions = get_condition(filters)
	sql = frappe.db.sql("""
		SELECT
			t.name,
			s.supplier_name as grouping,
			t.no_polisi,
			t.ticket_number as no_referensi,
			t.name as no_slip_timbang,
			t.driver_name as nama_supir,
			t.posting_date as tgl_masuk,
			t.weight_in_time as jam_masuk,
			t.posting_date as tgl_keluar,
			t.weight_out_time as jam_keluar,
			FORMAT(t.bruto, 2) as bruto,
			FORMAT(t.tara, 2) as tara,
			FORMAT(t.netto, 2) as netto_1,
			FORMAT(t.netto * (t.potongan_sortasi / 100), 2) as sort,
			FORMAT(0, 2) as netto_2,
			FORMAT(t.isi_komidel, 2) as bjr,
			FORMAT(0, 2) as grader
		FROM `tabTimbangan` t
		JOIN `tabSupplier` s ON s.name = t.supplier
		WHERE t.receive_type = "TBS Eksternal" AND t.supplier IS NOT NULL {};
	""".format(conditions), filters, as_dict=True)

	grouped = defaultdict(list)

	for row in sql:
		grouped[row["grouping"]].append(row)

	result = [
		{
			"grouping": key,
			"data": value
		}
		for key, value in grouped.items()
	]

	# frappe.throw(str(result))
	return result

def get_data_internal(filters):
	conditions = get_condition(filters)
	sql = frappe.db.sql("""
		SELECT
			t.name,
			spb.divisi as grouping,
			t.no_polisi,
			t.ticket_number as no_referensi,
			t.name as no_slip_timbang,
			t.driver_name as nama_supir,
			t.posting_date as tgl_masuk,
			t.weight_in_time as jam_masuk,
			t.posting_date as tgl_keluar,
			t.weight_out_time as jam_keluar,
			FORMAT(t.bruto, 2) as bruto,
			FORMAT(t.tara, 2) as tara,
			FORMAT(t.netto, 2) as netto_1,
			FORMAT(t.netto * (t.potongan_sortasi / 100), 2) as sort,
			FORMAT(0, 2) as netto_2,
			FORMAT(t.isi_komidel, 2) as bjr,
			FORMAT(0, 2) as grader
		FROM `tabTimbangan` t
		JOIN `tabSurat Pengantar Buah` as spb ON spb.name = t.spb
		WHERE t.receive_type = "TBS Internal" AND t.spb IS NOT NULL {};
	""".format(conditions), filters, as_dict=True)

	grouped = defaultdict(list)

	for row in sql:
		grouped[row["grouping"]].append(row)

	result = [
		{
			"grouping": key,
			"data": value
		}
		for key, value in grouped.items()
	]

	# frappe.throw(str(result))
	return result