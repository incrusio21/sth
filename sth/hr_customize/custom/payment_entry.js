// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.off("Payment Entry", "validate_reference_document");
frappe.ui.form.off("Payment Entry", "get_outstanding_documents");
frappe.ui.form.off("Payment Entry", "party");

frappe.ui.form.on("Payment Entry", {
	party: function (frm) {
		if (frm.doc.contact_email || frm.doc.contact_person) {
			frm.set_value("contact_email", "");
			frm.set_value("contact_person", "");
		}
		if (frm.doc.payment_type && frm.doc.party_type && frm.doc.party && frm.doc.company) {
			if (!frm.doc.posting_date) {
				frappe.msgprint(__("Please select Posting Date before selecting Party"));
				frm.set_value("party", "");
				return;
			}
			frm.set_party_account_based_on_party = true;

			let company_currency = frappe.get_doc(":Company", frm.doc.company).default_currency;

			return frappe.call({
				method: "erpnext.accounts.doctype.payment_entry.payment_entry.get_party_details",
				args: {
					company: frm.doc.company,
					party_type: frm.doc.party_type,
					party: frm.doc.party,
					date: frm.doc.posting_date,
					cost_center: frm.doc.cost_center,
				},
				callback: function (r, rt) {
					if (r.message) {
						frappe.run_serially([
							() => {
								if (frm.doc.payment_type == "Receive") {
									frm.set_value("paid_from", r.message.party_account);
									frm.set_value(
										"paid_from_account_currency",
										r.message.party_account_currency
									);
									frm.set_value("paid_from_account_balance", r.message.account_balance);
								} else if (frm.doc.payment_type == "Pay") {
									frm.set_value("paid_to", r.message.party_account);
									frm.set_value(
										"paid_to_account_currency",
										r.message.party_account_currency
									);
									frm.set_value("paid_to_account_balance", r.message.account_balance);
								}
							},
							() => frm.set_value("party_balance", r.message.party_balance),
							() => frm.set_value("party_name", r.message.party_name),

							() => frm.events.hide_unhide_fields(frm),
							() => frm.events.set_dynamic_labels(frm),
							() => {
								frm.set_party_account_based_on_party = false;
								if (r.message.party_bank_account) {
									frm.set_value("party_bank_account", r.message.party_bank_account);
								}
								if (r.message.bank_account) {
									frm.set_value("bank_account", r.message.bank_account);
								}
							},
							() =>
								frm.events.set_current_exchange_rate(
									frm,
									"source_exchange_rate",
									frm.doc.paid_from_account_currency,
									company_currency
								),
							() =>
								frm.events.set_current_exchange_rate(
									frm,
									"target_exchange_rate",
									frm.doc.paid_to_account_currency,
									company_currency
								),
						]);
					}
				},
			});
		}
	},
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
	payment_type(frm) {
		frm.set_value("bank_account", "")
		filter_bank_accounts(frm);
	},
	party_type(frm) {
		frm.set_value("internal_employee", 0)
	},
	unit(frm) {
		if (!frm.doc.unit) return
		filter_bank_accounts(frm);

	},
	internal_employee(frm) {
		if (!frm.doc.internal_employee) return

		frappe.call({
			method: "sth.hr_customize.custom.payment_entry.get_internal_employee",
			callback(data) {
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

frappe.ui.form.on("Payment Entry References", {
	refresh(frm,cdt,cdn){
		frm.set_query('reference_name', "references", function(doc, cdt, cdn) {
			let row = locals[cdt][cdn];
			
			if (row.reference_doctype) {
				let filters = {
					docstatus: 1,
					company: doc.company
				};
				
				if (row.reference_doctype === "Purchase Invoice" || row.reference_doctype === "Purchase Order") {
					if (doc.party_type === "Supplier" && doc.party) {
						filters.supplier = doc.party;
					}
				}
				else if (row.reference_doctype === "Sales Invoice" || row.reference_doctype === "Sales Order") {
					if (doc.party_type === "Customer" && doc.party) {
						filters.customer = doc.party;
					}
				}
				else if (row.reference_doctype === "Journal Entry") {
					if (doc.party_type && doc.party) {
						filters.pay_to_recd_from = doc.party;
					}
				}
				
				return {
					filters: filters
				};
			}
		});
	},
	reference_doctype(frm,cdt,cdn){
		frm.set_query('reference_name', "references", function(doc, cdt, cdn) {
			let row = locals[cdt][cdn];
			
			if (row.reference_doctype) {
				let filters = {
					docstatus: 1,
					company: doc.company
				};
				
				if (row.reference_doctype === "Purchase Invoice" || row.reference_doctype === "Purchase Order") {
					if (doc.party_type === "Supplier" && doc.party) {
						filters.supplier = doc.party;
					}
				}
				else if (row.reference_doctype === "Sales Invoice" || row.reference_doctype === "Sales Order") {
					if (doc.party_type === "Customer" && doc.party) {
						filters.customer = doc.party;
					}
				}
				else if (row.reference_doctype === "Journal Entry") {
					if (doc.party_type && doc.party) {
						filters.pay_to_recd_from = doc.party;
					}
				}
				
				return {
					filters: filters
				};
			}
		});
	}
	
})


function filter_bank_accounts(frm) {
    if (!frm.doc.unit) {
        return;
    }
    
    frappe.db.get_value('Unit', frm.doc.unit, 'bank_account', (r) => {
        if (r && r.bank_account) {
            let bank_account = r.bank_account;
            
            if (frm.doc.payment_type === 'Receive') {
                frm.set_query('paid_to', function() {
                    return {
                        filters: {
                            'name': bank_account
                        }
                    };
                });
                
                // Optionally set the value automatically
                frm.set_value('paid_to', bank_account);
                
            } else if (frm.doc.payment_type === 'Pay') {
                // Filter paid_from field
                frm.set_query('paid_from', function() {
                    return {
                        filters: {
                            'name': bank_account
                        }
                    };
                });
                
                // Optionally set the value automatically
                frm.set_value('paid_from', bank_account);
            }
        }
    });
    frappe.db.get_list('Bank Account', {
        filters: {
            'unit': frm.doc.unit
        },
        fields: ['name'],
        limit: 1
    }).then(records => {
        if (records && records.length > 0) {
            let bank_account_name = records[0].name;
            
            // Set the bank_account field
            frm.set_value('bank_account', bank_account_name);
            
            // Now get the account from Unit doctype for paid_to/paid_from
            frappe.db.get_value('Unit', frm.doc.unit, 'bank_account', (r) => {
                if (r && r.bank_account) {
                    let account = r.bank_account;
                    
                    if (frm.doc.payment_type === 'Receive') {
                        // Filter and set paid_to field
                        frm.set_query('paid_to', function() {
                            return {
                                filters: {
                                    'name': account
                                }
                            };
                        });
                        frm.set_value('paid_to', account);
                        
                    } else if (frm.doc.payment_type === 'Pay') {
                        // Filter and set paid_from field
                        frm.set_query('paid_from', function() {
                            return {
                                filters: {
                                    'name': account
                                }
                            };
                        });
                        frm.set_value('paid_from', account);
                    }
                }
            });
        }
    });
}