// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.off("Payment Entry", "validate_reference_document");
frappe.ui.form.off("Payment Entry", "get_outstanding_documents");
frappe.ui.form.off("Payment Entry", "party");
frappe.ui.form.off("Payment Entry", "mode_of_payment");

frappe.ui.form.on("Payment Entry", {
	setup(frm) {
		frm.set_query('path', function() {
			return {
				filters: {
					disabled: 0
				}
			};
		});
	},

	before_workflow_action: async function(frm) {
		if (
			frm.doc.workflow_state === "Butuh Persetujuan 2" &&
			frm.selected_workflow_action === "Approve"
		) {
			await check_mandiri_kcm_warning(frm);
		}
	},

	tipe_transfer: function(frm) {
		if (frm.doc.tipe_transfer == 'PDO') {
			show_pdo_selector(frm);
		} else if (frm.doc.tipe_transfer == 'Realisasi PDO') {
			show_realisasi_pdo_selector(frm);
		} else {
			frm.set_value('permintaan_dana_operasional', '');
		}
	},

	no_kendaraan: function(frm) {
		filter_paid_to_by_kendaraan(frm);
	},

	party: function(frm) {
		// Clear contact fields
		if (frm.doc.contact_email || frm.doc.contact_person) {
			frm.set_value("contact_email", "");
			frm.set_value("contact_person", "");
		}

		// Reset no_kontrak_penjualan jika party berubah
		if (frm.doc.party_type === "Customer") {
			frm.set_value("no_kontrak_penjualan", "");
		}

		set_no_rekening(frm);

		// Re-apply filter dengan customer baru
		frm.set_query("no_kontrak_penjualan", function() {
			return {
				filters: {
					customer: frm.doc.party || "",
					docstatus: 1,
					per_billed: ["<", 100],
					company: frm.doc.company
				},
			};
		});

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
				callback: function(r, rt) {
					if (r.message) {
						frappe.run_serially([
							() => {
								if (frm.doc.payment_type == "Receive") {
									frm.set_value("paid_from", r.message.party_account);
									frm.set_value("paid_from_account_currency", r.message.party_account_currency);
									frm.set_value("paid_from_account_balance", r.message.account_balance);
								} else if (frm.doc.payment_type == "Pay") {
									frm.set_value("paid_to", r.message.party_account);
									frm.set_value("paid_to_account_currency", r.message.party_account_currency);
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
							() => frm.events.set_current_exchange_rate(frm, "source_exchange_rate", frm.doc.paid_from_account_currency, company_currency),
							() => frm.events.set_current_exchange_rate(frm, "target_exchange_rate", frm.doc.paid_to_account_currency, company_currency),
						]);
					}
				},
			});
		}
	},

	permintaan_dana_operasional(frm) {
		if (frm.doc.tipe_transfer === 'Realisasi PDO' && frm.doc.permintaan_dana_operasional) {
			show_realisasi_sisa(frm);
		}
	},

	refresh: function(frm) {
		// Set reference_date pada dokumen baru
		if (
			frm.doc.__islocal &&
			!frm.doc.reference_date &&
			frm.doc.posting_date
		) {
			frm.set_value("reference_date", frm.doc.posting_date);
		}

		frm.set_query("no_kontrak_penjualan", function() {
			return {
				filters: {
					customer: frm.doc.party || "",
					docstatus: 1,
					per_billed: ["<", 100],
					company: frm.doc.company
				},
			};
		});

		if (frm.doc.docstatus == 0) {
			frm.add_custom_button(__("Pilih Nota Piutang"), function() {
				pick_nota_piutang(frm);
			}, __("Buat"));
		}

		frm.set_query("reference_doctype", "references", function() {
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
			};
		});

		frm.set_query('unit', (doc) => {
			return {
				filters: {
					company: ["=", doc.company],
				}
			};
		});

		frm.set_query('bank_account', (doc) => {
			return {
				filters: {
					unit: ["=", doc.unit],
					company: ["=", doc.company],
				}
			};
		});

		frm.set_query("payment_term", "references", function(frm, cdt, cdn) {
			const child = locals[cdt][cdn];
			let query = "sth.controllers.queries.get_payment_terms_for_references";
			if (
				["Purchase Invoice", "Sales Invoice"].includes(child.reference_doctype) &&
				child.reference_name
			) {
				query = "erpnext.controllers.queries.get_payment_terms_for_references";
			}
			return {
				query: query,
				filters: {
					reference: child.reference_name,
					reference_doctype: child.reference_doctype,
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
				} else if (row.reference_doctype === "Sales Invoice" || row.reference_doctype === "Sales Order") {
					if (doc.party_type === "Customer" && doc.party) {
						filters.customer = doc.party;
					}
				} else if (row.reference_doctype === "Journal Entry") {
					if (doc.party_type && doc.party) {
						filters.pay_to_recd_from = doc.party;
					}
				}

				return { filters: filters };
			}
		});

		frm.ignore_doctypes_on_cancel_all = ["Deposito Interest", "Deposito", "Disbursement Loan", "Installment Loan", "Payment Voucher Kas"];

		if (frm.doc.no_kendaraan) {
			filter_paid_to_by_kendaraan(frm);
		}

		check_mandiri_kcm(frm);
		toggle_paid_from_readonly(frm);
		// make_pdo_preview(frm)
	},

	payment_type(frm) {
		frm.set_value("bank_account", "");
		filter_bank_accounts(frm);
		toggle_paid_from_readonly(frm);
	},

	party_type: function(frm) {
		frm.set_value("internal_employee", 0);
		set_no_rekening(frm);
	},

	unit: function(frm) {
		pasang_company_account(frm);
		if (!frm.doc.unit) return;
		filter_bank_accounts(frm);
	},

	mode_of_payment(frm) {
		filter_bank_accounts(frm);
	},

	internal_employee(frm) {
		if (!frm.doc.internal_employee) return;

		frappe.call({
			method: "sth.hr_customize.custom.payment_entry.get_internal_employee",
			callback(data) {
				frm.set_value("party", data.message);
			}
		});

		frm.set_df_property('paid_from', 'read_only', 0);
	},

	paid_from: function(frm) {
		check_mandiri_kcm(frm);
		set_ft_service(frm);
	},

	paid_to: function(frm) {
		set_ft_service(frm);
	},

	ft_service: function(frm) {
		if (frm.doc.ft_service === "UBP") {
			frm.set_value("path", "MCM_BillPaymentSingle");
		} else {
			frm.set_value("path", "MCM_SingleMix");
		}
	},

	company: function(frm) {
		frm.set_query("no_kontrak_penjualan", function() {
			return {
				filters: {
					customer: frm.doc.party || "",
					docstatus: 1,
					per_billed: ["<", 100],
					company: frm.doc.company
				},
			};
		});
	},

	no_payroll_entry(frm) {
		if (!frm.doc.no_payroll_entry) return;

		frappe.call({
			method: "sth.overrides.payroll_entry.get_payroll_entry_for_payment",
			args: { payroll_entry: frm.doc.no_payroll_entry },
			freeze: true,
			freeze_message: __("Mengambil data Payroll Entry..."),
			callback(r) {
				if (!r.message) return;

				const d = r.message;

				frm.set_value("payment_type", "Internal Transfer");
				frm.set_value("company",                  d.company);
				frm.set_value("paid_to",                  d.paid_to);
				frm.set_value("paid_to_account_currency", d.paid_to_account_currency);
				frm.set_value("paid_amount",              d.paid_amount);
				frm.set_value("received_amount",          d.received_amount);
				frm.set_value("remarks",                  d.remarks);

				if (d.cost_center) {
					frm.set_value("cost_center", d.cost_center);
				}
			}
		});
	},

	no_kontrak_penjualan: function(frm) {
		if (!frm.doc.no_kontrak_penjualan) return;
		frm.set_value("paid_from", "");
		frappe.db.get_doc("Sales Order", frm.doc.no_kontrak_penjualan).then(so => {
			frm.set_value("party_type", "Customer");
			frm.set_value("party", so.customer);

			frappe.db.get_list("Account", {
				filters: {
					company: frm.doc.company,
					account_name: ["like", "%Uang Muka Penjualan%"],
					is_group: 0,
				},
				fields: ["name"],
				limit: 1,
			}).then(accounts => {
				frm.set_value("paid_from", accounts[0].name);
			});

			const first_term = so.payment_schedule && so.payment_schedule[0];
			if (!first_term) {
				frappe.msgprint("Tidak ada payment schedule di Sales Order ini.");
				return;
			}

			let nilai_dp = first_term.payment_amount;

			frm.set_value("paid_amount", nilai_dp);
			frm.set_value("received_amount", nilai_dp);

			category_tax = "%Excluding PPN%";
			if (so.taxes) {
				if (so.taxes[0].included_in_print_rate == 1) {
					category_tax = "%Including PPN%";
				}
			}

			frappe.db.get_list("Sales Taxes and Charges Template", {
				filters: {
					company: frm.doc.company,
					title: ["like", category_tax],
					disabled: 0,
				},
				limit: 1,
			}).then(templates => {
				if (!templates || !templates.length) {
					frappe.msgprint("Template PPN tidak ditemukan.");
					return;
				}

				frappe.db.get_doc("Sales Taxes and Charges Template", templates[0].name).then(template_doc => {
					let taxes = template_doc.taxes;
					if (!taxes || !taxes.length) {
						frappe.msgprint("Tidak ada baris pajak di template PPN.");
						return;
					}

					frm.clear_table("deductions");
					let ppn_total = 0;
					const is_inclusive = so.taxes && so.taxes[0] && so.taxes[0].included_in_print_rate == 1;

					taxes.forEach(tax => {
						let amount;
						if (is_inclusive) {
							const dpp = nilai_dp / (1 + tax.rate / 100);
							amount = nilai_dp - dpp;
						} else {
							amount = nilai_dp * tax.rate / 100;
						}
						ppn_total += amount;

						frappe.db.get_value("Company", frm.doc.company, "cost_center").then(r => {
							const cost_center = r.message && r.message.cost_center;
							frm.add_child("deductions", {
								account: tax.account_head,
								cost_center: cost_center,
								amount: amount * -1,
							});
							frm.refresh_field("deductions");

							if (is_inclusive) {
								frm.set_value("paid_amount", nilai_dp);
								frm.set_value("received_amount", nilai_dp);
							} else {
								const total = nilai_dp + ppn_total;
								frm.set_value("paid_amount", total);
								frm.set_value("received_amount", total);
							}
						});
					});
				});
			});
		});
	},

	validate_reference_document: function(frm, row) {
		var _validate = function(i, row) {
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

	get_outstanding_documents: function(frm, filters, get_outstanding_invoices, get_orders_to_be_billed) {
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
			callback: function(r, rt) {
				if (r.message) {
					var total_positive_outstanding = 0;
					var total_negative_outstanding = 0;
					$.each(r.message, function(i, d) {
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
	payment_term(frm, cdt, cdn) {
		let row = locals[cdt][cdn];

		frappe.call({
			method: "sth.hr_customize.custom.payment_entry.get_payment_term_outstanding",
			args: {
				doctype: row.reference_doctype,
				reference: row.reference_name,
				payment_term: row.payment_term,
			},
			callback: function(r) {
				if (r.message) {
					frappe.model.set_value(cdt, cdn, "payment_term_outstanding", r.message);
				}
			},
		});
	},

	reference_name(frm, cdt, cdn) {
		let row = locals[cdt][cdn];

		if (row.reference_doctype !== "Ganti Rugi Lahan" || !row.reference_name) return;

		frappe.call({
			method: "sth.legal.doctype.ganti_rugi_lahan.ganti_rugi_lahan.get_next_payment_schedule",
			args: {
				reference_doctype: row.reference_doctype,
				reference_name: row.reference_name,
				exclude_payment_entry: frm.doc.name,
			},
			callback: function(r) {
				if (!r.message) return;

				frappe.model.set_value(cdt, cdn, "payment_term", r.message.payment_term);
				frappe.model.set_value(cdt, cdn, "allocated_amount", r.message.allocated_amount);
				frappe.model.set_value(cdt, cdn, "payment_term_outstanding", r.message.payment_term_outstanding);

				sync_paid_amount_from_references(frm);
			},
		});
	}
});

function sync_paid_amount_from_references(frm) {
	const total_allocated = (frm.doc.references || []).reduce((sum, d) => sum + flt(d.allocated_amount), 0);
	frm.set_value("paid_amount", total_allocated);
	frm.set_value("received_amount", total_allocated);
}


function set_no_rekening(frm) {
	let paid_to = null;

	if (frm.doc.payment_type === "Internal Transfer") {
		paid_to = frm.doc.paid_to;
	}

	frappe.call({
		method: "sth.custom.payment_entry.get_no_rekening",
		args: {
			party_type: frm.doc.party_type,
			party: frm.doc.party,
			paid_to: paid_to,
			tipe_transfer: frm.doc.tipe_transfer,
			permintaan_dana_operasional: frm.doc.permintaan_dana_operasional,
			payment_type: frm.doc.payment_type
		},
		callback: function(r) {
			if (r.message) {
				frm.set_value("no_rekening",         r.message.no_rekening || "");
				frm.set_value("nama_bank",           r.message.nama_bank || "");
				frm.set_value("no_rekening_tujuan",  r.message.no_rekening_tujuan || "");
				frm.set_value("bank_tujuan",         r.message.bank_tujuan || "");
			} else {
				frm.set_value("no_rekening", "");
				frm.set_value("nama_bank", "");
				frm.set_value("no_rekening_tujuan", "");
				frm.set_value("bank_tujuan", "");
			}
		}
	});
}

function pick_nota_piutang(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Pilih Nota Piutang"),
		fields: [
			{
				fieldtype: "Link",
				fieldname: "nota_piutang",
				label: "Nota Piutang",
				options: "Nota Piutang",
				reqd: 1,
				get_query() {
					return {
						filters: {
							tipe: "Pemenuhan Kontrak",
							docstatus: 1,
						}
					};
				}
			}
		],
		primary_action_label: __("Terapkan"),
		primary_action(values) {
			dialog.hide();
			apply_nota_piutang(frm, values.nota_piutang);
		}
	});

	dialog.show();
}

async function apply_nota_piutang(frm, nota_piutang_name) {
	try {
		const np = await frappe.db.get_doc("Nota Piutang", nota_piutang_name);
		frm.set_value("unit", np.unit);

		const si_from_main = (np.nota_hutang_pemenuhan_kontrak_table || [])
			.filter(row => row.pengakuan_penjualan)
			.map(row => row.pengakuan_penjualan);

		const si_from_reclass = (np.reclass_pengakuan_penjualan || [])
			.filter(row => row.pengakuan_penjualan_ppn)
			.map(row => row.pengakuan_penjualan_ppn);

		const all_si_names = [...new Set([...si_from_main, ...si_from_reclass])];

		if (all_si_names.length === 0) {
			frappe.throw(__("Nota Piutang ini tidak memiliki Sales Invoice."));
		}

		const si_docs = await Promise.all(
			all_si_names.map(name => frappe.db.get_doc("Sales Invoice", name))
		);

		const payable_si = si_docs.filter(si => flt(si.outstanding_amount) > 0);

		if (payable_si.length === 0) {
			frappe.throw(__("Semua Sales Invoice pada Nota Piutang ini sudah lunas."));
		}

		const total_outstanding = payable_si.reduce(
			(sum, si) => sum + flt(si.outstanding_amount), 0
		);

		frm.set_value("nota_piutang_pemenuhan_kontrak", np.name);

		if (!frm.doc.party) {
			await frm.set_value("party_type", "Customer");
			await frm.set_value("party", payable_si[0].customer);
		}

		if (np.unit) {
			const unit_doc = await frappe.db.get_doc("Unit", np.unit);
			if (unit_doc.bank_account) {
				await frm.set_value("paid_to", unit_doc.bank_account);
			}
		}

		frm.clear_table("references");

		for (const si of payable_si) {
			const row = frm.add_child("references");
			row.reference_doctype = "Sales Invoice";
			row.reference_name = si.name;
			row.bill_no = si.bill_no || "";
			row.due_date = si.due_date;
			row.total_amount = flt(si.grand_total);
			row.outstanding_amount = flt(si.outstanding_amount);
			row.allocated_amount = flt(si.outstanding_amount);
		}

		frm.refresh_field("references");

		frm.set_value("paid_amount", total_outstanding);
		frm.set_value("received_amount", total_outstanding);

		frappe.show_alert({
			message: __(`Nota Piutang <b>${np.name}</b> berhasil diterapkan.`),
			indicator: "green"
		}, 4);

	} catch (err) {
		frappe.msgprint({
			title: __("Error"),
			message: err.message || JSON.stringify(err),
			indicator: "red"
		});
	}
}

function pasang_company_account(frm) {
	if (frm.doc.unit) {
		frappe.db.get_value('Unit', frm.doc.unit, 'default_bank_account', function(r) {
			if (r && r.default_bank_account) {
				frm.set_value('bank_account', r.default_bank_account);
			} else {
				frm.set_value('bank_account', '');
			}
		});
	} else {
		frm.set_value('bank_account', '');
	}
}

function make_pdo_preview(frm) {
	const rows = frm.doc.payment_voucher_kas_pdo || [];
	if (rows.length === 0) return;

	const uniquePDO = [...new Set(
		rows
			.map(r => r.no_pdo)
			.filter(v => v && v.trim() !== '')
	)];

	if (uniquePDO.length === 0) return;

	frm.add_custom_button(__('Check Preview'), function() {
		show_pdo_preview(uniquePDO);
	}, __('PDO'));
}

function show_pdo_preview(pdoList) {
	const baseUrl = 'https://sth.digitalasiasolusindo.com/printview'
		+ '?doctype=Permintaan%20Dana%20Operasional'
		+ '&format=PF%20Preview%20PDO'
		+ '&no_letterhead=0'
		+ '&trigger_print=0';

	let html = '<div style="display:flex; flex-direction:column; gap:10px; padding: 10px 0;">';

	pdoList.forEach(pdo => {
		const url = `${baseUrl}&name=${encodeURIComponent(pdo)}`;
		html += `
			<div style="display:flex; justify-content:space-between; align-items:center;
						padding: 10px 14px; border: 1px solid #d1d8dd; border-radius: 6px;">
				<span style="font-weight:500;">${frappe.utils.escape_html(pdo)}</span>
				<a href="${url}" target="_blank" class="btn btn-sm btn-primary">
					<i class="fa fa-external-link"></i>&nbsp; Open Preview
				</a>
			</div>`;
	});

	html += '</div>';

	new frappe.ui.Dialog({
		title: __('PDO Preview'),
		fields: [{
			fieldtype: 'HTML',
			fieldname: 'preview_html',
			options: html
		}]
	}).show();
}

function check_mandiri_kcm(frm) {
	if (!frm.doc.paid_from) {
		frm.set_df_property('mandiri_kcm', 'hidden', 1);
		return;
	}

	frappe.call({
		method: 'sth.custom.payment_entry.is_mandiri_kcm',
		args: {
			account: frm.doc.paid_from
		},
		callback: function(r) {
			let is_mandiri_kcm = r.message ? 0 : 1;
			frm.set_df_property('mandiri_kcm', 'hidden', is_mandiri_kcm);
		}
	});
}

async function set_ft_service(frm) {
	let paid_from = frm.doc.paid_from;

	if (!paid_from) {
		return;
	}

	try {
		let from_bank_account = await frappe.db.get_value(
			'Bank Account',
			{ account: paid_from },
			['bank']
		);

		let from_bank = from_bank_account.message?.bank;

		if (!from_bank) {
			frm.set_value('ft_service', 'InHouse Transfer');
			return;
		}

		let rekening = await frappe.call({
			method: "sth.custom.payment_entry.get_no_rekening",
			args: {
				party_type: frm.doc.party_type,
				party: frm.doc.party,
				paid_to: frm.doc.payment_type === "Internal Transfer"
					? frm.doc.paid_to
					: null
			}
		});

		let to_bank =
			rekening.message?.bank_tujuan ||
			rekening.message?.nama_bank;

		if (!to_bank) {
			frm.set_value('ft_service', 'InHouse Transfer');
			return;
		}

		frm.set_value(
			'ft_service',
			from_bank !== to_bank
				? 'Online Domestic Transfer'
				: 'InHouse Transfer'
		);

	} catch (e) {
		console.log(e);
		frm.set_value('ft_service', 'InHouse Transfer');
	}
}

async function check_mandiri_kcm_warning(frm) {
	let r = await frappe.call({
		method: "sth.bank_payment.custom.payment_entry.get_mandiri_kcm_warnings",
		args: {
			payment_entry: frm.doc.name
		}
	});

	let data = r.message || {};

	if (!data.has_warning) {
		return;
	}

	const field_labels = {
		beneficiary_account: "beneficiary_account / No Rekening Tujuan",
		debit_account: "debit_account / No Rekening",
		beneficiary_name: "beneficiary_name / Nama Penerima",
		bank_code: "bank_code / Kode Bank",
		amount: "amount / Nominal",
		currency: "currency / Mata Uang"
	};

	let missing_fields = (data.missing_fields || []).map(
		field => field_labels[field] || field
	);

	return new Promise((resolve, reject) => {
		// console.log("freeze count", frappe.dom.freeze_count);

		frappe.dom.unfreeze();

		// console.log("after unfreeze", frappe.dom.freeze_count);

		frappe.confirm(
			`
			Mandatory field Mandiri KCM belum lengkap:
			<br><br>
			<b>${missing_fields.join("<br>")}</b>
			<br><br>
			Proses Mandiri KCM kemungkinan gagal.
			<br><br>
			Apakah Anda ingin melanjutkan?
			`,
			() => resolve(),
			async () => {
				await frm.reload_doc();
				reject();
			}
		);
	});
}

function toggle_paid_from_readonly(frm) {
	let is_readonly = ["Internal Transfer", "Pay"].includes(frm.doc.payment_type) ? 1 : 0;
	frm.set_df_property('paid_from', 'read_only', is_readonly);
}

function filter_bank_accounts(frm) {
	if (!frm.doc.unit || !frm.doc.mode_of_payment || !frm.doc.company) {
		return;
	}

	frappe.db.get_value(
		'Unit',
		frm.doc.unit,
		['bank_account', 'account_for_cash'],
		(unit_res) => {
			let mop = frm.doc.mode_of_payment.toLowerCase();
			let is_cash = mop.includes("cash");

			let selected_account = null;

			if (is_cash) {
				selected_account = unit_res.account_for_cash;
			} else {
				selected_account = unit_res.bank_account;
			}

			if (!selected_account) {
				let msg = is_cash
					? `Account Cash di Unit <b>${frm.doc.unit}</b> belum diisi.<br>Mencoba menggunakan default cash account dari Company.`
					: `Account Bank di Unit <b>${frm.doc.unit}</b> belum diisi.<br>Mencoba menggunakan default bank account dari Company.`;

				frappe.db.get_value(
					'Company',
					frm.doc.company,
					['default_bank_account', 'default_cash_account'],
					(comp_res) => {
						if (is_cash) {
							selected_account = comp_res.default_cash_account;
						} else {
							selected_account = comp_res.default_bank_account;
						}

						if (!selected_account) {
							let err_msg = is_cash
								? `Default Cash Account di Company <b>${frm.doc.company}</b> juga belum diisi.<br>Silakan lengkapi pengaturan Account terlebih dahulu.`
								: `Default Bank Account di Company <b>${frm.doc.company}</b> juga belum diisi.<br>Silakan lengkapi pengaturan Account terlebih dahulu.`;

							frappe.msgprint({
								title: "Account Tidak Ditemukan",
								message: err_msg,
								indicator: "red"
							});

							apply_account(frm, null);
							return;
						}

						apply_account(frm, selected_account);
					}
				);
			} else {
				apply_account(frm, selected_account);
			}
		}
	);
}

function filter_paid_to_by_kendaraan(frm) {
	if (!frm.doc.no_kendaraan) {
		frm.set_query('paid_to', function() {
			return { filters: { is_group: 0 } };
		});
		return;
	}

	frappe.db.get_value('Alat Berat Dan Kendaraan', frm.doc.no_kendaraan, 'tipe_master', (r) => {
		let prefix = (r && r.tipe_master === 'Kendaraan Umum') ? '7' : '4';

		frm.set_query('paid_to', function() {
			return {
				filters: {
					is_group: 0,
					account_number: ['like', prefix + '%'],
				}
			};
		});

		frappe.show_alert({
			message: __('Filter <b>Paid To</b> menampilkan akun berawalan <b>') + prefix + '</b>.',
			indicator: 'blue',
		});
	});
}

function apply_account(frm, account) {
	if (frm.doc.payment_type == 'Receive' || (frm.doc.payment_type == 'Internal Transfer' && (frm.doc.tipe_transfer == "Penerimaan Dana PDO" || frm.doc.tipe_transfer == "Dividen Receive"))) {

		frm.set_query('paid_to', function() {
			return account ? { filters: { name: account } } : {};
		});

		frm.set_value('paid_to', account || "");

	} else if (frm.doc.payment_type == 'Pay' || (frm.doc.payment_type == 'Internal Transfer' && (frm.doc.tipe_transfer == "Payroll Entry" || frm.doc.tipe_transfer == "Realisasi PDO" || frm.doc.tipe_transfer == "PDO" || frm.doc.tipe_transfer == "Dividen Sent" || frm.doc.tipe_transfer == "Leasing"))) {

		frm.set_query('paid_from', function() {
			return account ? { filters: { name: account } } : {};
		});

		frm.set_value('paid_from', account || "");
	}
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
				frm.set_value('paid_amount', pdo.grand_total_pdo);
				frm.set_value('received_amount', pdo.grand_total_pdo);
				frm.refresh_fields();
				frappe.show_alert({
					message: __('PDO {0} linked successfully', [name]),
					indicator: 'green'
				});
			}
		}
	});
}

function show_realisasi_sisa(frm) {
	let pdo_name = frm.doc.permintaan_dana_operasional;
	if (!pdo_name) return;

	frappe.db.get_value(
		'Permintaan Dana Operasional',
		pdo_name,
		[
			'grand_total_bahan_bakar', 'grand_total_perjalanan_dinas',
			'grand_total_kas', 'grand_total_dana_cadangan',
			'outstanding_amount_bahan_bakar', 'outstanding_amount_perjalanan_dinas',
			'outstanding_amount_kas', 'outstanding_amount_dana_cadangan'
		],
		function(d) {
			if (!d) return;

			let paid = flt(frm.doc.paid_amount);

			let tipes = [
				{ label: 'Bahan Bakar',      grand: d.grand_total_bahan_bakar,       outstanding: d.outstanding_amount_bahan_bakar },
				{ label: 'Perjalanan Dinas', grand: d.grand_total_perjalanan_dinas,  outstanding: d.outstanding_amount_perjalanan_dinas },
				{ label: 'Kas',              grand: d.grand_total_kas,               outstanding: d.outstanding_amount_kas },
				{ label: 'Dana Cadangan',    grand: d.grand_total_dana_cadangan,     outstanding: d.outstanding_amount_dana_cadangan },
			].filter(t => flt(t.grand) > 0);

			let total_outstanding = tipes.reduce((s, t) => s + flt(t.outstanding), 0);
			let sisa_setelah_bayar = total_outstanding - paid;

			let rows = tipes.map(t => {
				let sisa = flt(t.outstanding);
				let color = sisa > 0 ? '#e74c3c' : '#27ae60';
				return `
					<tr>
						<td style="padding:4px 8px;">${t.label}</td>
						<td style="padding:4px 8px; text-align:right;">${format_currency(flt(t.grand))}</td>
						<td style="padding:4px 8px; text-align:right; color:${color}; font-weight:bold;">${format_currency(sisa)}</td>
					</tr>
				`;
			}).join('');

			let sisa_color = sisa_setelah_bayar > 0 ? '#e74c3c' : '#27ae60';
			let html = `
				<div style="background:#f9f9f9; border:1px solid #ddd; border-radius:4px; padding:10px; margin-bottom:10px; font-size:13px;">
					<b>Sisa Realisasi PDO: ${pdo_name}</b>
					<table style="width:100%; margin-top:6px; border-collapse:collapse;">
						<thead>
							<tr style="background:#eee;">
								<th style="padding:4px 8px; text-align:left;">Tipe</th>
								<th style="padding:4px 8px; text-align:right;">Grand Total</th>
								<th style="padding:4px 8px; text-align:right;">Sisa (Outstanding)</th>
							</tr>
						</thead>
						<tbody>${rows}</tbody>
						<tfoot>
							<tr style="border-top:2px solid #ccc; font-weight:bold;">
								<td style="padding:4px 8px;">Total</td>
								<td></td>
								<td style="padding:4px 8px; text-align:right; color:${sisa_color};">
									${format_currency(sisa_setelah_bayar)}
									<small style="font-weight:normal;">(setelah bayar ${format_currency(paid)})</small>
								</td>
							</tr>
						</tfoot>
					</table>
				</div>
			`;

			frappe.msgprint({
				title: __('Sisa Realisasi PDO'),
				message: html,
				indicator: sisa_setelah_bayar > 0 ? 'yellow' : 'green'
			});
		}
	);
}

function format_currency(value) {
	return frappe.format(value, { fieldtype: 'Currency' });
}

function show_realisasi_pdo_selector(frm) {
	frappe.call({
		method: 'frappe.client.get_list',
		args: {
			doctype: 'Permintaan Dana Operasional',
			filters: [
				['docstatus', '=', 1],
				['payment_voucher_kebun', '!=', ''],
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

				let tipe_options = [];
				tipe_options.push('Bahan Bakar');
				tipe_options.push('Perjalanan Dinas');
				tipe_options.push('Kas');
				tipe_options.push('Dana Cadangan');

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

						// Kalau PE sudah tersimpan, isi langsung — jangan buat PE baru
						if (!frm.doc.__islocal) {
							let amount_map = {
								'Bahan Bakar':      flt(outstanding_bb),
								'Perjalanan Dinas': flt(outstanding_pd),
								'Kas':              flt(outstanding_kas),
								'Dana Cadangan':    flt(outstanding_dc),
							};
							let amount = amount_map[values.tipe_pdo] || 0;

							frappe.db.get_doc('Permintaan Dana Operasional', selected_name).then(pdo => {
								frm.clear_table('payment_voucher_kas_pdo');

								let tipe_table_map = {
									'Bahan Bakar':      'pdo_bahan_bakar',
									'Perjalanan Dinas': 'pdo_perjalanan_dinas',
									'Kas':              'pdo_kas',
									'Dana Cadangan':    'pdo_dana_cadangan',
								};
								let table_name = tipe_table_map[values.tipe_pdo];
								let rows = (table_name && pdo[table_name]) || [];

								rows.forEach(row => {
									frm.add_child('payment_voucher_kas_pdo', {
										no_pdo:   selected_name,
										tipe_pdo: values.tipe_pdo,
										debit_to: row.debit_to,
										penerima: row.employee,
										total:    row.total,
									});
								});

								frm.refresh_field('payment_voucher_kas_pdo');
								frm.set_value('permintaan_dana_operasional', selected_name);
								frm.set_value('paid_amount', amount);
								frm.set_value('received_amount', amount);
							});
							return;
						}

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

function sum_payment_voucher_kas_pdo(frm) {
	let sum = (frm.doc.payment_voucher_kas_pdo || [])
		.reduce((s, r) => s + flt(r.total), 0);
	frm.set_value("paid_amount", sum);
	frm.set_value("received_amount", sum);
}

frappe.ui.form.on("Payment Voucher Kas PDO", {
	total(frm, cdt, cdn) {
		sum_payment_voucher_kas_pdo(frm);
	},
	payment_voucher_kas_pdo_remove(frm) {
		sum_payment_voucher_kas_pdo(frm);
	}
});
