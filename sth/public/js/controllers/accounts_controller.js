// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt
frappe.provide("sth.plantation");

sth.plantation.AccountsController = class AccountsController extends frappe.ui.form.Controller {
    show_general_ledger() {
		let me = this;
		if(this.frm.doc.docstatus > 0) {
			cur_frm.add_custom_button(__('Accounting Ledger'), function() {
				frappe.route_options = {
					voucher_no: me.frm.doc.name,
					from_date: me.frm.doc.posting_date,
					to_date: moment(me.frm.doc.modified).format('YYYY-MM-DD'),
					company: me.frm.doc.company,
					categorize_by: "Categorize by Voucher (Consolidated)",
					show_cancelled_entries: me.frm.doc.docstatus === 2,
					ignore_prepared_report: true
				};
				frappe.set_route("query-report", "General Ledger");
			}, __("View"));
		}
	}

}