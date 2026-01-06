# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	q_laporan_angsuran_pinjaman_bank = frappe.db.sql("""
		SELECT
		sb.company as customer,
		ilb.disbursement_number as no_pinjaman,
		sb.type as fas,
		sb.currency as ccy,
		ilb.disbursement_amount as outstanding,
		ilb.disbursement_date as from_date,
		ilb.days as days,
		ilb.payment_date as to_date,
		CONCAT(ROUND(ilb.loan_interest, 2), ' %') as ir,
		ilb.principal as pokok,
		ilb.interest_amount as bunga,
		ilb.payment_total as total_kewajiban
		FROM `tabLoan Bank` as sb
		JOIN `tabInstallment Loan Bank` as ilb ON ilb.parent = sb.name;
  """, as_dict=True)

	for loan in q_laporan_angsuran_pinjaman_bank:
		data.append(loan)

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("bulan"):
		conditions += " AND DATE_FORMAT(dit.posting_date, '%%b') = %(bulan)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("CUSTOMER"),
			"fieldtype": "Data",
			"fieldname": "customer",
		},
		{
			"label": _("No.Pinjaman"),
			"fieldtype": "Data",
			"fieldname": "no_pinjaman",
		},
		{
			"label": _("FAS"),
			"fieldtype": "Data",
			"fieldname": "fas",
		},
		{
			"label": _("Ccy"),
			"fieldtype": "Data",
			"fieldname": "ccy",
		},
		{
			"label": _("Outstanding"),
			"fieldtype": "Currency",
			"fieldname": "outstanding",
		},
		{
			"label": _("From"),
			"fieldtype": "Date",
			"fieldname": "from_date",
		},
		{
			"label": _("Days"),
			"fieldtype": "Data",
			"fieldname": "days",
		},
		{
			"label": _("To /Tgl Pembayaran"),
			"fieldtype": "Date",
			"fieldname": "to_date",
		},
		{
			"label": _("IR"),
			"fieldtype": "Data",
			"fieldname": "ir",
		},
		{
			"label": _("Pokok"),
			"fieldtype": "Currency",
			"fieldname": "pokok",
		},
		{
			"label": _("Bunga"),
			"fieldtype": "Currency",
			"fieldname": "bunga",
		},
		{
			"label": _("Total Kewajiban"),
			"fieldtype": "Currency",
			"fieldname": "total_kewajiban",
		},
	]

	return columns