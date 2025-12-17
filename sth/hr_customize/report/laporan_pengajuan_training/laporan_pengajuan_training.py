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
		name as no_training,
		company as perusahaan,
		`type` as kategori_training,
		name as nama_training,
		custom_posting_date as tanggal_training,
		custom_grand_total_costing as biaya,
		supplier as lembaga_pelatihan
		FROM `tabTraining Event` as te
		WHERE te.company IS NOT NULL {};
  """.format(conditions), filters, as_dict=True)

	for training in query_l_pengajuan_training:
		data.append(training);

	return columns, data

def get_condition(filters):
	conditions = "AND te.company = %(company)s"

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