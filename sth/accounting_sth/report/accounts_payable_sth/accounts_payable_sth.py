# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


from sth.accounting_sth.report.accounts_receivable_sth.accounts_receivable_sth import ReceivablePayableReport


def execute(filters=None):
	args = {
		"account_type": "Payable",
		"naming_by": ["Buying Settings", "supp_master_name"],
	}
	return ReceivablePayableReport(filters).run(args)
