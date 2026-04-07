// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.off("Payment Entry", "validate_reference_document");
frappe.ui.form.off("Payment Entry", "get_outstanding_documents");
frappe.ui.form.off("Payment Entry", "party");

frappe.ui.form.on("Payment Entry", {
	tipe_transfer: function(frm) {
        if (frm.doc.tipe_transfer == 'PDO') {
            show_pdo_selector(frm);
        } 
        else if (frm.doc.tipe_transfer == 'Realisasi PDO') {
            show_realisasi_pdo_selector(frm);
        }
        else {
            // Clear PDO field if another type is selected
            frm.set_value('permintaan_dana_operasional', '');
        }
    },
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

		frm.set_query("payment_term", "references", function (frm, cdt, cdn) {
			const child = locals[cdt][cdn];
            let query = "sth.controllers.queries.get_payment_terms_for_references"
			if (
				["Purchase Invoice", "Sales Invoice"].includes(child.reference_doctype) &&
				child.reference_name
			) {
                query = "erpnext.controllers.queries.get_payment_terms_for_references"
            }
            return {
                query: query,
                filters: {
                    reference: child.reference_name,
                },
            };
		});

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

frappe.ui.form.on("Payment Entry Reference", {
	payment_term(frm, cdt, cdn){
		let row = locals[cdt][cdn];

		frappe.call({
			method: "sth.hr_customize.custom.payment_entry.get_payment_term_outstanding",
			args: {
				doctype: row.reference_doctype,
				reference: row.reference_name,
				payment_term: row.payment_term,
			},
			callback: function (r) {
				if (r.message) {
					frappe.model.set_value(cdt, cdn, "payment_term_outstanding", r.message)
				}
			},
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

    frappe.db.get_value('Unit', frm.doc.unit, 'default_bank_account', (r) => {
        if (r && r.default_bank_account) {
            let default_bank_account = r.default_bank_account;
            frm.set_value('bank_account', default_bank_account);            
        }
    });
    
    
}

function show_pdo_selector(frm) {
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Permintaan Dana Operasional',
            filters: [
                ['docstatus', '=', 1],
                ['payment_voucher', '=', '']
            ],
            fields: ['name', 'posting_date', 'unit', 
                     'grand_total_bahan_bakar', 
                     'grand_total_perjalanan_dinas', 
                     'grand_total_kas', 
                     'grand_total_dana_cadangan', 
                     'grand_total_non_pdo'],
            limit: 50
        },
        callback: function(r) {
            if (!r.message || r.message.length === 0) {
                frappe.msgprint({
                    title: __('No PDO Available'),
                    message: __('There are no submitted PDO without payment voucher.'),
                    indicator: 'orange'
                });
                frm.set_value('tipe_transfer', '');
                return;
            }

            let rows = r.message.map(d => {
                let total = (d.grand_total_bahan_bakar || 0) +
                            (d.grand_total_perjalanan_dinas || 0) +
                            (d.grand_total_kas || 0) +
                            (d.grand_total_dana_cadangan || 0) +
                            (d.grand_total_non_pdo || 0);
                return `
                    <tr class="pdo-row" 
                        data-name="${d.name}"
                        style="cursor:pointer;">
                        <td style="padding:8px; border-bottom:1px solid #eee;">${d.name}</td>
                        <td style="padding:8px; border-bottom:1px solid #eee;">${d.unit || '-'}</td>
                        <td style="padding:8px; border-bottom:1px solid #eee;">${d.posting_date}</td>
                        <td style="padding:8px; border-bottom:1px solid #eee; text-align:right;">
                            ${frappe.format(total, {fieldtype: 'Currency'})}
                        </td>
                    </tr>
                `;
            }).join('');

            let dialog = new frappe.ui.Dialog({
                title: __('Select PDO'),
                fields: [{
                    fieldtype: 'HTML',
                    fieldname: 'pdo_table',
                    options: `
                        <table style="width:100%; border-collapse:collapse;">
                            <thead>
                                <tr style="background:#f5f5f5; font-weight:bold;">
                                    <th style="padding:8px; text-align:left;">PDO</th>
                                    <th style="padding:8px; text-align:left;">Unit</th>
                                    <th style="padding:8px; text-align:left;">Date</th>
                                    <th style="padding:8px; text-align:right;">Grand Total</th>
                                </tr>
                            </thead>
                            <tbody>${rows}</tbody>
                        </table>
                    `
                }]
            });

            dialog.show();

            // ↓ THIS IS WHERE THE CLICK HANDLER GOES
            dialog.$wrapper.find('.pdo-row').on('click', function() {
                let selected_name = $(this).data('name');
                dialog.hide();

                frappe.call({
                    method: 'sth.finance_sth.doctype.permintaan_dana_operasional.permintaan_dana_operasional.create_payment_voucher',
                    args: {
                        source_name: selected_name
                    },
                    freeze: true,
                    freeze_message: __('Creating Payment Voucher...'),
                    callback: function(r) {
                        if (r.message) {
                            var doc = r.message;
                            frappe.model.sync(doc);
                            frappe.set_route('Form', 'Payment Entry', doc.name);
                        }
                    }
                });
            });
        }
    });
}

function fetch_pdo_details(frm, pdo_name) {
    let name = pdo_name || frm.doc.pdo_reference;
    if (!name) return;

    frappe.call({
        method: 'frappe.client.get',
        args: {
            doctype: 'Permintaan Dana Operasional',
            name: name
        },
        callback: function(r) {
            if (r.message) {
                let pdo = r.message;
                // Map PDO fields to Payment Entry fields
                frm.set_value('paid_amount', pdo.grand_total_pdo);
                frm.set_value('received_amount', pdo.grand_total_pdo);
                // Add other field mappings as needed
                // frm.set_value('party', pdo.party);
                // frm.set_value('cost_center', pdo.cost_center);

                frm.refresh_fields();
                frappe.show_alert({
                    message: __('PDO {0} linked successfully', [name]),
                    indicator: 'green'
                });
            }
        }
    });
}

function show_realisasi_pdo_selector(frm) {
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Permintaan Dana Operasional',
            filters: [
                ['docstatus', '=', 1],
                ['payment_voucher', '!=', '']
            ],
            fields: [
                'name', 'posting_date', 'unit',
                'grand_total_bahan_bakar',
                'grand_total_perjalanan_dinas',
                'grand_total_kas',
                'grand_total_dana_cadangan',
                'outstanding_amount_bahan_bakar',
                'outstanding_amount_perjalanan_dinas',
                'outstanding_amount_kas',
                'outstanding_amount_dana_cadangan'
            ],
            limit: 50
        },
        callback: function(r) {
            if (!r.message || r.message.length === 0) {
                frappe.msgprint({
                    title: __('No PDO Available'),
                    message: __('There are no submitted PDO with payment voucher.'),
                    indicator: 'orange'
                });
                frm.set_value('tipe_transfer', '');
                return;
            }

            // Only show PDOs that have at least one outstanding tipe
            let available_pdos = r.message.filter(d => {
                return (d.outstanding_amount_bahan_bakar > 0) ||
                       (d.outstanding_amount_perjalanan_dinas > 0) ||
                       (d.outstanding_amount_kas > 0) ||
                       (d.outstanding_amount_dana_cadangan > 0);
            });

            if (available_pdos.length === 0) {
                frappe.msgprint({
                    title: __('No PDO Available'),
                    message: __('All PDOs have been fully realized.'),
                    indicator: 'orange'
                });
                frm.set_value('tipe_transfer', '');
                return;
            }

            let rows = available_pdos.map(d => {
                let grand_total = (d.grand_total_bahan_bakar || 0) +
                                  (d.grand_total_perjalanan_dinas || 0) +
                                  (d.grand_total_kas || 0) +
                                  (d.grand_total_dana_cadangan || 0);

                let outstanding = (d.outstanding_amount_bahan_bakar || 0) +
                                  (d.outstanding_amount_perjalanan_dinas || 0) +
                                  (d.outstanding_amount_kas || 0) +
                                  (d.outstanding_amount_dana_cadangan || 0);

                return `
                    <tr class="pdo-row"
                        data-name="${d.name}"
                        data-bb="${d.outstanding_amount_bahan_bakar || 0}"
                        data-pd="${d.outstanding_amount_perjalanan_dinas || 0}"
                        data-kas="${d.outstanding_amount_kas || 0}"
                        data-dc="${d.outstanding_amount_dana_cadangan || 0}"
                        style="cursor:pointer;">
                        <td style="padding:8px; border-bottom:1px solid #eee;">${d.name}</td>
                        <td style="padding:8px; border-bottom:1px solid #eee;">${d.unit || '-'}</td>
                        <td style="padding:8px; border-bottom:1px solid #eee;">${d.posting_date}</td>
                        <td style="padding:8px; border-bottom:1px solid #eee; text-align:right;">
                            ${frappe.format(grand_total, {fieldtype: 'Currency'})}
                        </td>
                        <td style="padding:8px; border-bottom:1px solid #eee; text-align:right; color: #e74c3c;">
                            ${frappe.format(outstanding, {fieldtype: 'Currency'})}
                        </td>
                    </tr>
                `;
            }).join('');

            let dialog = new frappe.ui.Dialog({
                title: __('Select PDO for Realisasi'),
                fields: [{
                    fieldtype: 'HTML',
                    fieldname: 'pdo_table',
                    options: `
                        <table style="width:100%; border-collapse:collapse;">
                            <thead>
                                <tr style="background:#f5f5f5; font-weight:bold;">
                                    <th style="padding:8px; text-align:left;">PDO</th>
                                    <th style="padding:8px; text-align:left;">Unit</th>
                                    <th style="padding:8px; text-align:left;">Date</th>
                                    <th style="padding:8px; text-align:right;">Grand Total</th>
                                    <th style="padding:8px; text-align:right;">Outstanding</th>
                                </tr>
                            </thead>
                            <tbody>${rows}</tbody>
                        </table>
                    `
                }]
            });

            dialog.show();

            dialog.$wrapper.find('.pdo-row').on('click', function() {
                let selected_name = $(this).data('name');
                let outstanding_bb = $(this).data('bb');
                let outstanding_pd = $(this).data('pd');
                let outstanding_kas = $(this).data('kas');
                let outstanding_dc = $(this).data('dc');

                dialog.hide();

                // Build tipe_pdo options based on which ones have outstanding amount
                let tipe_options = [];
                if (outstanding_bb > 0) tipe_options.push('Bahan Bakar');
                if (outstanding_pd > 0) tipe_options.push('Perjalanan Dinas');
                if (outstanding_kas > 0) tipe_options.push('Kas');
                if (outstanding_dc > 0) tipe_options.push('Dana Cadangan');

                let tipe_dialog = new frappe.ui.Dialog({
                    title: __('Select Tipe PDO'),
                    fields: [
                        {
                            fieldtype: 'HTML',
                            fieldname: 'pdo_info',
                            options: `<p style="margin-bottom:10px;">
                                        PDO: <strong>${selected_name}</strong>
                                      </p>`
                        },
                        {
                            label: __('Tipe PDO'),
                            fieldname: 'tipe_pdo',
                            fieldtype: 'Select',
                            options: tipe_options.join('\n'),
                            reqd: 1
                        }
                    ],
                    primary_action_label: __('Create Realisasi'),
                    primary_action: function(values) {
                        tipe_dialog.hide();

                        frappe.call({
                            method: 'sth.finance_sth.doctype.permintaan_dana_operasional.permintaan_dana_operasional.create_payment_voucher_alokasi',
                            args: {
                                source_name: selected_name,
                                tipe_pdo: values.tipe_pdo
                            },
                            freeze: true,
                            freeze_message: __('Creating Realisasi PDO...'),
                            callback: function(r) {
                                if (r.message) {
                                    var doc = r.message;
                                    frappe.model.sync(doc);
                                    frappe.set_route('Form', 'Payment Entry', doc.name);
                                }
                            }
                        });
                    }
                });

                tipe_dialog.show();
            });
        }
    });
}