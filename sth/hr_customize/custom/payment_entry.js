// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.off("Payment Entry", "validate_reference_document");
frappe.ui.form.off("Payment Entry", "get_outstanding_documents");
frappe.ui.form.on("Payment Entry", {
    refresh(frm) {
        frm.set_query("reference_doctype", "references", function () {
            return {
                query: "sth.hr_customize.custom.payment_entry.get_payment_reference",
                filters: { 
                    party_type: frm.doc.party_type 
                },
            };
        });
        
        frm.set_query('custom_cheque_number', () => {
            return {
                filters: {
                    reference_doc: ["=", null], 
                    reference_name: ["=", null], 
                    bank_account: ["=", frm.doc.bank_account] 
                }
            }
        })
        
        frm.set_query('unit', (doc) => {
            return {
                filters: {
                    company: ["=", doc.company],
                }
            }
        })

        frm.set_query('reference_name', "references", (doc) => {
            return {
                filters: {
                    docstatus: 1,
                    company: ["=", doc.company],
                    unit: doc.unit   
                }
            }
        })

        frm.set_query('bank_account', (doc) => {
            return {
                filters: {
                    unit: ["=", doc.unit],
                    company: ["=", doc.company],
                }
            }
        })
        frm.ignore_doctypes_on_cancel_all = ["Deposito Interest", "Deposito", "Disbursement Loan", "Installment Loan", "Payment Voucher Kas"];
    },
	payment_type(frm){
        frm.set_value("bank_account", "")
    },
    party_type(frm){
        frm.set_value("internal_employee", 0)
    },
    unit(frm){
        if(!frm.doc.unit) return
        
        // frm.clear_table("references")
        // frm.refresh_field("references")
    },
    internal_employee(frm){
        if(!frm.doc.internal_employee) return

        frappe.call({
            method: "sth.hr_customize.custom.payment_entry.get_internal_employee",
            callback(data){
                frm.set_value("party", data.message)
            }
        })
    },

    validate_reference_document: function (frm, row) {
		var _validate = function (i, row) {
			if (!row.reference_doctype) {
				return;
			}

			if (
				frm.doc.party_type == "Customer" &&
				!["Sales Order", "Sales Invoice", "Journal Entry", "Dunning", "Deposito Interest", "Disbursement Loan", "Payment Voucher Kas"].includes(row.reference_doctype)
			) {
				frappe.model.set_value(row.doctype, row.name, "reference_doctype", null);
				frappe.msgprint(
					__(
						"Row #{0}: Reference Document Type must be one of Sales Order, Sales Invoice, Journal Entry or Dunning, Deposito Interest, Disbursement Loan",
						[row.idx]
					)
				);
				return false;
			}

			if (
				frm.doc.party_type == "Supplier" &&
				!["Purchase Order", "Purchase Invoice", "Journal Entry"].includes(row.reference_doctype)
			) {
				frappe.model.set_value(row.doctype, row.name, "against_voucher_type", null);
				frappe.msgprint(
					__(
						"Row #{0}: Reference Document Type must be one of Purchase Order, Purchase Invoice or Journal Entry",
						[row.idx]
					)
				);
				return false;
			}
		};

		if (row) {
			_validate(0, row);
		} else {
			$.each(frm.doc.vouchers || [], _validate);
		}
	},

	get_outstanding_documents: function (frm, filters, get_outstanding_invoices, get_orders_to_be_billed) {
		frm.clear_table("references");

		if (!frm.doc.party) {
			return;
		}

		frm.events.check_mandatory_to_fetch(frm);
		var company_currency = frappe.get_doc(":Company", frm.doc.company).default_currency;

		var args = {
			posting_date: frm.doc.posting_date,
			company: frm.doc.company,
			party_type: frm.doc.party_type,
			payment_type: frm.doc.payment_type,
			party: frm.doc.party,
			party_account: frm.doc.payment_type == "Receive" ? frm.doc.paid_from : frm.doc.paid_to,
			cost_center: frm.doc.cost_center,
            unit: frm.doc.unit
		};

		for (let key in filters) {
			args[key] = filters[key];
		}

		if (get_outstanding_invoices) {
			args["get_outstanding_invoices"] = true;
		} else if (get_orders_to_be_billed) {
			args["get_orders_to_be_billed"] = true;
		}

		if (frm.doc.book_advance_payments_in_separate_party_account) {
			args["book_advance_payments_in_separate_party_account"] = true;
		}

		frappe.flags.allocate_payment_amount = filters["allocate_payment_amount"];

		return frappe.call({
			method: "sth.custom.payment_entry.get_outstanding_reference_documents",
			args: {
				args: args,
			},
			callback: function (r, rt) {
				if (r.message) {
					var total_positive_outstanding = 0;
					var total_negative_outstanding = 0;
					$.each(r.message, function (i, d) {
						var c = frm.add_child("references");
						c.reference_doctype = d.voucher_type;
						c.reference_name = d.voucher_no;
						c.due_date = d.due_date;
						c.total_amount = d.invoice_amount;
						c.outstanding_amount = d.outstanding_amount;
						c.bill_no = d.bill_no;
						c.payment_term = d.payment_term;
						c.payment_term_outstanding = d.payment_term_outstanding;
						c.allocated_amount = d.allocated_amount;
						c.account = d.account;

						if (!in_list(frm.events.get_order_doctypes(frm), d.voucher_type)) {
							if (flt(d.outstanding_amount) > 0)
								total_positive_outstanding += flt(d.outstanding_amount);
							else total_negative_outstanding += Math.abs(flt(d.outstanding_amount));
						}

						var party_account_currency =
							frm.doc.payment_type == "Receive"
								? frm.doc.paid_from_account_currency
								: frm.doc.paid_to_account_currency;

						if (party_account_currency != company_currency) {
							c.exchange_rate = d.exchange_rate;
						} else {
							c.exchange_rate = 1;
						}
						if (in_list(frm.events.get_invoice_doctypes(frm), d.reference_doctype)) {
							c.due_date = d.due_date;
						}
					});

					if (
						(frm.doc.payment_type == "Receive" && frm.doc.party_type == "Customer") ||
						(frm.doc.payment_type == "Pay" && frm.doc.party_type == "Supplier") ||
						(frm.doc.payment_type == "Pay" && frm.doc.party_type == "Employee")
					) {
						if (total_positive_outstanding > total_negative_outstanding)
							if (!frm.doc.paid_amount)
								frm.set_value(
									"paid_amount",
									total_positive_outstanding - total_negative_outstanding
								);
					} else if (
						total_negative_outstanding &&
						total_positive_outstanding < total_negative_outstanding
					) {
						if (!frm.doc.received_amount)
							frm.set_value(
								"received_amount",
								total_negative_outstanding - total_positive_outstanding
							);
					}
				}

				frm.events.allocate_party_amount_against_ref_docs(
					frm,
					frm.doc.payment_type == "Receive" ? frm.doc.paid_amount : frm.doc.received_amount,
					false
				);
			},
		});
	},
});
