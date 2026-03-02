// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt
frappe.provide("sth.plantation");

sth.plantation.AccountsController = class AccountsController extends frappe.ui.form.Controller {
    show_general_ledger() {
		let me = this;
		if(this.frm.doc.docstatus > 0) {
			this.frm.add_custom_button(__('Accounting Ledger'), function() {
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

	get_company_currency() {
		return erpnext.get_currency(this.frm.doc.company);
	}
    
    currency() {
		// The transaction date be either transaction_date (from orders) or posting_date (from invoices)
		let transaction_date = this.frm.doc.transaction_date || this.frm.doc.posting_date;
		let inter_company_reference = this.frm.doc.inter_company_order_reference || this.frm.doc.inter_company_invoice_reference;

		let me = this;
		this.set_dynamic_labels();
		let company_currency = this.get_company_currency();
		// Added `load_after_mapping` to determine if document is loading after mapping from another doc
		if(this.frm.doc.currency && this.frm.doc.currency !== company_currency
				&& (!this.frm.doc.__onload?.load_after_mapping || inter_company_reference)) {

			this.get_exchange_rate(transaction_date, this.frm.doc.currency, company_currency,
				function(exchange_rate) {
					if(exchange_rate != me.frm.doc.conversion_rate) {
						me.set_margin_amount_based_on_currency(exchange_rate);
						me.set_actual_charges_based_on_currency(exchange_rate);
						me.frm.set_value("conversion_rate", exchange_rate);
					}
				});
		} else {
			// company currency and doc currency is same
			// this will prevent unnecessary conversion rate triggers
			if(this.frm.doc.currency === this.get_company_currency()) {
				this.frm.set_value("conversion_rate", 1.0);
			} else {
				this.conversion_rate();
			}
		}
	}

	set_dynamic_labels() {
		// What TODO? should we make price list system non-mandatory?
		// this.frm.toggle_reqd("plc_conversion_rate",
		// 	!!(this.frm.doc.price_list_name && this.frm.doc.price_list_currency));

		var company_currency = this.get_company_currency();
		this.change_form_labels(company_currency);
		// this.change_grid_labels(company_currency);
		this.frm.refresh_fields();
	}

	change_form_labels(company_currency) {
		let me = this;

		// this.frm.set_currency_labels(["base_total", "base_net_total", "base_total_taxes_and_charges",
		// 	"base_discount_amount", "base_grand_total", "base_rounded_total", "base_in_words",
		// 	"base_taxes_and_charges_added", "base_taxes_and_charges_deducted", "total_amount_to_pay",
		// 	"base_paid_amount", "base_write_off_amount", "base_change_amount", "base_operating_cost",
		// 	"base_raw_material_cost", "base_total_cost", "base_scrap_material_cost",
		// 	"base_rounding_adjustment"], company_currency);

		// this.frm.set_currency_labels(["total", "net_total", "total_taxes_and_charges", "discount_amount",
		// 	"grand_total", "taxes_and_charges_added", "taxes_and_charges_deducted","tax_withholding_net_total",
		// 	"rounded_total", "in_words", "paid_amount", "write_off_amount", "operating_cost",
		// 	"scrap_material_cost", "rounding_adjustment", "raw_material_cost",
		// 	"total_cost"], this.frm.doc.currency);

		// this.frm.set_currency_labels(["outstanding_amount", "total_advance"],
		// 	this.frm.doc.party_account_currency);

		this.frm.set_df_property("conversion_rate", "description", "1 " + this.frm.doc.currency
			+ " = [?] " + company_currency);

		// if(this.frm.doc.price_list_currency && this.frm.doc.price_list_currency!=company_currency) {
		// 	this.frm.set_df_property("plc_conversion_rate", "description", "1 "
		// 		+ this.frm.doc.price_list_currency + " = [?] " + company_currency);
		// }

		// toggle fields
		this.frm.toggle_display(["conversion_rate"],
		this.frm.doc.currency != company_currency);

		// this.frm.toggle_display(["plc_conversion_rate", "price_list_currency"],
		// 	this.frm.doc.price_list_currency != company_currency);

		// let show = cint(this.frm.doc.discount_amount) ||
		// 		((this.frm.doc.taxes || []).filter(function(d) {return d.included_in_print_rate===1}).length);

		// if(this.frm.doc.doctype && frappe.meta.get_docfield(this.frm.doc.doctype, "net_total")) {
		// 	this.frm.toggle_display("net_total", show);
		// }

		// if(this.frm.doc.doctype && frappe.meta.get_docfield(this.frm.doc.doctype, "base_net_total")) {
		// 	this.frm.toggle_display("base_net_total", (show && (me.frm.doc.currency != company_currency)));
		// }
	}

}