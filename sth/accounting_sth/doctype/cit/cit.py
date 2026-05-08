# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
from erpnext.accounts.report.financial_statements import get_data, get_period_list
from frappe.model.document import Document

class CIT(Document):
	pass

@frappe.whitelist()
def get_profit_for_year(company, tahun):
    fiscal_year = frappe.get_doc("Fiscal Year", tahun)

    period_list = get_period_list(
        from_fiscal_year=tahun,
        to_fiscal_year=tahun,
        period_start_date=fiscal_year.year_start_date,
        period_end_date=fiscal_year.year_end_date,
        filter_based_on="Fiscal Year",
        periodicity="Yearly",
        company=company,
    )

    filters = frappe._dict({
        "company": company,
        "from_fiscal_year": tahun,
        "to_fiscal_year": tahun,
        "period_start_date": fiscal_year.year_start_date,
        "period_end_date": fiscal_year.year_end_date,
        "filter_based_on": "Fiscal Year",
        "periodicity": "Yearly",
        "accumulated_values": 1,
        "presentation_currency": None,
        "accumulated_in_group_company": 0,
    })

    income = get_data(
        company,
        "Income",
        "Credit",
        period_list,
        filters=filters,
        accumulated_values=1,
        ignore_closing_entries=True,
    )

    expense = get_data(
        company,
        "Expense",
        "Debit",
        period_list,
        filters=filters,
        accumulated_values=1,
        ignore_closing_entries=True,
    )

    # Hitung net profit langsung, tanpa import dari P&L module
    last_key = period_list[-1].key

    total_income  = flt(income[-2].get(last_key),  3) if income  else 0.0
    total_expense = flt(expense[-2].get(last_key), 3) if expense else 0.0

    net_profit = total_income - total_expense

    return net_profit

@frappe.whitelist()
def get_account_balance(company, account, year_end):
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(debit - credit), 0)
        FROM `tabGL Entry`
        WHERE company      = %s
          AND account      = %s
          AND posting_date <= %s
          AND is_cancelled = 0
          AND docstatus    = 1
    """, (company, account, year_end))
    return result[0][0] or 0