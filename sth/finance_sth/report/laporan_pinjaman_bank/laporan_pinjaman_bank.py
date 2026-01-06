# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	q_laporan_pinjam_bank = frappe.db.sql("""
		SELECT
		dlb.disbursement_date as est_pay_date,
		dlb.disbursement_date as act_pay_date,
		dlb.disbursement_amount as withdrawal,
		dlb.disbursement_total as outstanding,
		ilb.principal + ilb.interest_amount as act_total_pay,
		ilb.principal as principal,
		ilb.loan_interest as interest_rate,
		ilb.interest_amount as interest,
		lb.loan_amount - dlb.disbursement_amount as ending_balance,
		dlb.disbursement_amount as cumulative_interest
		FROM `tabLoan Bank` as lb
		JOIN `tabDisbursement Loan Bank` as dlb ON dlb.parent = lb.name
		JOIN `tabInstallment Loan Bank` as ilb ON ilb.disbursement_number = dlb.disbursement_number;
  """, as_dict=True)

	for loan in q_laporan_pinjam_bank:
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
			"label": _("Est Payment Date"),
			"fieldtype": "Date",
			"fieldname": "est_pay_date",
		},
		{
			"label": _("Act Payment Date"),
			"fieldtype": "Date",
			"fieldname": "act_pay_date",
		},
		{
			"label": _("Withdrawal"),
			"fieldtype": "Currency",
			"fieldname": "withdrawal",
		},
		{
			"label": _("Outstanding"),
			"fieldtype": "Currency",
			"fieldname": "outstanding",
		},
		{
			"label": _("Est Total Payment"),
			"fieldtype": "Currency",
			"fieldname": "est_total_pay",
		},
		{
			"label": _("Act Total Payment"),
			"fieldtype": "Currency",
			"fieldname": "act_total_pay",
		},
		{
			"label": _("Principal"),
			"fieldtype": "Currency",
			"fieldname": "principal",
		},
		{
			"label": _("Interest Rate"),
			"fieldtype": "Data",
			"fieldname": "interest_rate",
		},
		{
			"label": _("Interest"),
			"fieldtype": "Currency",
			"fieldname": "interest",
		},
		{
			"label": _("Admin Fee"),
			"fieldtype": "Currency",
			"fieldname": "admin_fee",
		},
		{
			"label": _("Others"),
			"fieldtype": "Currency",
			"fieldname": "others",
		},
		{
			"label": _("Ending Balance"),
			"fieldtype": "Currency",
			"fieldname": "ending_balance",
		},
		{
			"label": _("Cumulative Interest"),
			"fieldtype": "Currency",
			"fieldname": "cumulative_interest",
		},
	]

	return columns