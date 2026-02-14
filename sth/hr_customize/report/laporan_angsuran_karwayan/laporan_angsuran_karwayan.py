# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	query_l_angsuran_karyawan = frappe.db.sql("""
		SELECT
		e.name as nik,
		l.company as pt,
		e.unit as unit,
		e.employee_name as nama,
		lp.product_name as jenis_angsuran,
		l.loan_amount as total_nilai_hutang,
		lrs.repayment_start_date as bulan_awal,
		lrs.maturity_date as sampai,
		lrs.repayment_periods as jumlah_bulan,
		lrs.monthly_repayment_amount as potongan_per_bulan,
		lrs.total_installments_paid * lrs.monthly_repayment_amount as jumlah_potongan_berjalan
		FROM `tabLoan` as l
		JOIN `tabEmployee` as e ON e.name = l.applicant
		JOIN `tabLoan Product` as lp ON lp.name = l.loan_product
		JOIN `tabLoan Repayment Schedule` as lrs ON lrs.loan = l.name
		WHERE l.company IS NOT NULL {};
  """.format(conditions), filters, as_dict=True)

	for loan in query_l_angsuran_karyawan:
		data.append(loan);

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("from_date") and filters.get("to_date"):
		conditions += " AND l.posting_date BETWEEN %(from_date)s AND %(to_date)s"

	if filters.get("nama_karyawan"):
		conditions += " AND e.name = %(nama_karyawan)s"

	if filters.get("unit"):
		conditions += " AND e.unit = %(unit)s"

	if filters.get("company"):
		conditions += " AND l.company = %(company)s"

	if filters.get("jenis_angsuran"):
		conditions += " AND l.loan_product = %(jenis_angsuran)s"

	if filters.get("jenis_angsuran"):
		conditions += " AND l.loan_product = %(jenis_angsuran)s"

	if filters.get("status"):
		conditions += " AND l.status = %(status)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("NIK"),
			"fieldtype": "Data",
			"fieldname": "nik",
		},
		{
			"label": _("PT"),
			"fieldtype": "Data",
			"fieldname": "pt",
		},
		{
			"label": _("Unit"),
			"fieldtype": "Data",
			"fieldname": "unit",
		},
		{
			"label": _("Nama"),
			"fieldtype": "Data",
			"fieldname": "nama",
		},
		{
			"label": _("Jenis Angsuran"),
			"fieldtype": "Data",
			"fieldname": "jenis_angsuran",
		},
		{
			"label": _("Total Nilai Hutang (Rp.)"),
			"fieldtype": "Currency",
			"fieldname": "total_nilai_hutang",
		},
		{
			"label": _("Bulan Awal"),
			"fieldtype": "Date",
			"fieldname": "bulan_awal",
		},
		{
			"label": _("Sampai"),
			"fieldtype": "Date",
			"fieldname": "sampai",
		},
		{
			"label": _("Jumlah (Bulan)"),
			"fieldtype": "Data",
			"fieldname": "jumlah_bulan",
		},
		{
			"label": _("Potongan/Bulan. (Rp.)"),
			"fieldtype": "Currency",
			"fieldname": "potongan_per_bulan",
		},
		{
			"label": _("Jumlah Potongan Berjalan"),
			"fieldtype": "Currency",
			"fieldname": "jumlah_potongan_berjalan",
		},
	]

	return columns