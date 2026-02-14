# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	query_l_pengajuan_training = frappe.db.sql("""
    SELECT
    te.name as no_training,
    te.company as perusahaan,
    te.type as kategori_training,
    te.name as nama_training,
    te.custom_posting_date as tanggal_training,
    te.custom_grand_total_costing as biaya,
    te.supplier as lembaga_pelatihan,
    tee.employee_name as peserta_training
    FROM `tabTraining Event` as te
    LEFT JOIN `tabTraining Event Employee` as tee ON tee.parent = te.name
		WHERE te.company IS NOT NULL {};
  """.format(conditions), filters, as_dict=True)
	grouped = {}

	for row in query_l_pengajuan_training:
		key = row["no_training"]

		if key not in grouped:
			grouped[key] = {
				"no_training": row["no_training"],
				"perusahaan": row["perusahaan"],
				"kategori_training": row["kategori_training"],
				"nama_training": row["nama_training"],
				"tanggal_training": row["tanggal_training"],
				"biaya": row["biaya"],
				"lembaga_pelatihan": row["lembaga_pelatihan"],
				"peserta_training": [],
			}

		if row.get("peserta_training"):
			grouped[key]["peserta_training"].append(row["peserta_training"])

	result = list(grouped.values())

	for training in result:
		data.append({
			"no_training": training["no_training"],
			"perusahaan": training["perusahaan"],
			"kategori_training": training["kategori_training"],
			"nama_training": training["nama_training"],
			"tanggal_training": training["tanggal_training"],
			"biaya": training["biaya"],
			"lembaga_pelatihan": training["lembaga_pelatihan"],
			"peserta_training": ", ".join(training["peserta_training"])
    });

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("company"):
		conditions += " AND te.company = %(company)s"

	if filters.get("kategori_training"):
		conditions += " AND te.type = %(kategori_training)s"

	if filters.get("from_date") and filters.get("to_date"):
		conditions += " AND te.custom_posting_date BETWEEN %(from_date)s AND %(to_date)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("No Training"),
			"fieldtype": "Data",
			"fieldname": "no_training",
		},
		{
			"label": _("Perusahaan"),
			"fieldtype": "Data",
			"fieldname": "perusahaan",
		},
		{
			"label": _("Kategori Training"),
			"fieldtype": "Data",
			"fieldname": "kategori_training",
		},
		{
			"label": _("Nama Training"),
			"fieldtype": "Data",
			"fieldname": "nama_training",
		},
		{
			"label": _("Tanggal Training"),
			"fieldtype": "Date",
			"fieldname": "tanggal_training",
		},
		{
			"label": _("Biaya"),
			"fieldtype": "Currency",
			"fieldname": "biaya",
		},
		{
			"label": _("Lembaga Pelatihan"),
			"fieldtype": "Data",
			"fieldname": "lembaga_pelatihan",
		},
		{
			"label": _("Peserta Training"),
			"fieldtype": "Data",
			"fieldname": "peserta_training",
		},
	]

	return columns