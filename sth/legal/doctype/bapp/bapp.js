// Copyright (c) 2026, DAS and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("erpnext.stock");

cur_frm.cscript.tax_table = "Purchase Taxes and Charges";

erpnext.accounts.taxes.setup_tax_filters("Purchase Taxes and Charges");
erpnext.accounts.taxes.setup_tax_validations("BAPP");
erpnext.buying.setup_buying_controller();

{% include 'sth/legal/custom/tax_validation.js' %}

frappe.ui.form.on("BAPP", {
	setup: (frm) => {
		frm.custom_make_buttons = {
			"Purchase Invoice": "Purchase Invoice",
		};

		frm.set_query("unit", function () {
			return {
				filters: { company: ["=", frm.doc.company] },
			};
		});

		frm.set_query("expense_account", "items", function () {
			return {
				query: "erpnext.controllers.queries.get_expense_account",
				filters: { company: frm.doc.company },
			};
		});

		frm.set_query("wip_composite_asset", "items", function () {
			return {
				filters: { is_composite_asset: 1, docstatus: 0 },
			};
		});

		frm.set_query("taxes_and_charges", function () {
			return {
				filters: { company: frm.doc.company },
			};
		});

		frm.set_query("termin", function (doc) {
			return {
				filters: {
					for_proposal: 1,
				},
			};
		});
	},
	onload: function (frm) {
		erpnext.queries.setup_queries(frm, "Warehouse", function () {
			return erpnext.queries.warehouse(frm.doc);
		});
	},

	refresh: function (frm) {
		if (frm.doc.company) {
			frm.trigger("toggle_display_account_head");
		}

		if (frm.doc.docstatus === 0) {
			if (!frm.doc.is_return) {
				frappe.db.get_single_value("Buying Settings", "maintain_same_rate").then((value) => {
					if (value) {
						frm.doc.items.forEach((item) => {
							frm.fields_dict.items.grid.update_docfield_property(
								"rate",
								"read_only",
								item.proposal && item.proposal_item
							);
						});
					}
				});
			}
		}

		frm.events.add_custom_buttons(frm);
	},

	add_custom_buttons: function (frm) {
		
	},

	company: function (frm) {
		frm.trigger("toggle_display_account_head");
		erpnext.accounts.dimensions.update_dimension(frm, frm.doctype);
	},

	toggle_display_account_head: function (frm) {
		var enabled = erpnext.is_perpetual_inventory_enabled(frm.doc.company);
		frm.fields_dict["items"].grid.set_column_disp(["cost_center"], enabled);
	},
});

frappe.ui.form.on("BAPP", {
	refresh: function (frm) {
		frm.set_query("ppn",(doc) => {
			return {
				filters: {
					"type": "PPN"
				}
			}
		})

		frm.set_query("type", "pph_details",(doc) => {
			return {
				filters: {
					"type": "PPh"
				}
			}
		})
	},
	ppn: function (frm) {
		frappe.call({
			method: "sth.utils.data.tax_rate",
			args: {
				tax_name: frm.doc.ppn,
				company: frm.doc.company,
				type: "Masukan",
			},
			callback: function(r){
				if(r.message){
					frm.doc.ppn_rate = r.message.rate
					frm.doc.ppn_account = r.message.account
					frm.doc.ppn_amount = flt(frm.doc.net_total * (frm.doc.ppn_rate / 100));
				}
				recreate_tax_table(frm)
			}
		})
	}
})

erpnext.stock.BAPPController = class BAPPController extends (
	erpnext.buying.BuyingController
) {
	setup(doc) {
		this.setup_posting_date_time_check();
		super.setup(doc);
	}

	refresh() {
		var me = this;
		super.refresh();

		erpnext.accounts.ledger_preview.show_accounting_ledger_preview(this.frm);

		if (this.frm.doc.docstatus > 0) {
			this.show_general_ledger();

			this.frm.add_custom_button(
				__("Asset"),
				function () {
					frappe.route_options = {
						bapp: me.frm.doc.name,
					};
					frappe.set_route("List", "Asset");
				},
				__("View")
			);

			this.frm.add_custom_button(
				__("Asset Movement"),
				function () {
					frappe.route_options = {
						reference_name: me.frm.doc.name,
					};
					frappe.set_route("List", "Asset Movement");
				},
				__("View")
			);
		}

		if (this.frm.doc.status != "Closed") {
			if (this.frm.doc.docstatus == 0) {
				this.frm.add_custom_button(
					__("Proposal"),
					function () {
						if (!me.frm.doc.supplier) {
							frappe.throw({
								title: __("Mandatory"),
								message: __("Please Select a Supplier"),
							});
						}

						let d = new frappe.ui.Dialog({
							title: 'Get Proposal',
							fields: [
								{
									label: 'Supplier',
									fieldname: 'supplier',
									fieldtype: 'Link',
									options: 'Supplier',
									default: me.frm.doc.supplier,
									onchange: function () {
										d.set_value("proposal", "")
									}
								},
								{
									label: 'Proposal',
									fieldname: 'proposal',
									fieldtype: 'Link',
									options: 'Proposal',
									reqd: 1,
									get_query: () => {
										let filters = {                                        
											docstatus: 1,
											status: ["not in", ["Closed", "On Hold"]],
											per_received: ["<", 99.99],
											company: me.frm.doc.company
										}
										if (d.get_value("supplier")){
											filters["supplier"] = d.get_value("supplier")
										}
										return {
											filters: filters
										};
									},
									onchange: function () {
										frappe.call({
											method: "sth.legal.custom.purchase_invoice.get_proposal_termin",
											args: { proposal: this.value },
											callback: (r) => {
												if (!r.exc) {
													d.set_value("termin", "")
													d.fields_dict.termin.df.options = r.message
													d.fields_dict.termin.set_options()
												}
											},
										});
									}
								},
								{
									label: 'Termin',
									fieldname: 'termin',
									fieldtype: 'Select',
								}
							],
							primary_action_label: 'Get Items',
							primary_action(values) {
								cur_frm.doc.items = []
								
								frappe.call({
									// Sometimes we hit the limit for URL length of a GET request
									// as we send the full target_doc. Hence this is a POST request.
									type: "POST",
									method: "frappe.model.mapper.map_docs",
									args: {
										method: "sth.legal.doctype.proposal.proposal.make_bapp",
										source_names: [values.proposal],
										target_doc: cur_frm.doc,
										args: {
											term: values.termin
										},
									},
									freeze: true,
									freeze_message: __("Mapping {0} ...", ["Proposal"]),
									callback: function (r) {
										if (!r.exc) {
											frappe.model.sync(r.message);
											cur_frm.dirty();
											cur_frm.refresh();
										}
									},
								});
								d.hide();
							}
						});

						d.show()
					},
					__("Get Items From")
				);
			}

			if (this.frm.doc.docstatus == 1 && this.frm.doc.status != "Closed") {
				if (this.frm.has_perm("submit")) {
					cur_frm.add_custom_button(__("Close"), this.close_bapp, __("Status"));
				}

				if (flt(this.frm.doc.per_billed) < 100) {
					cur_frm.add_custom_button(
						__("Purchase Invoice"),
						() => this._make_pi_with_supplier_dialog(cur_frm),
						__("Create")
					);
				}

				cur_frm.page.set_inner_btn_group_as_primary(__("Create"));
			}
		}

		if (this.frm.doc.docstatus == 1 && this.frm.doc.status === "Closed" && this.frm.has_perm("submit")) {
			cur_frm.add_custom_button(__("Reopen"), this.reopen_bapp, __("Status"));
		}

		this.frm.toggle_reqd("supplier_warehouse", this.frm.doc.is_old_subcontracting_flow);
	}

	// Ganti kedua method lama dengan ini saja
	_make_pi_with_supplier_dialog(frm) {
		// Step 1: ambil kontraktor & pengeluaran barang secara paralel
		Promise.all([
			frm.doc.proposal
				? frappe.db.get_doc("Proposal", frm.doc.proposal).then(doc => {
					// Ganti "kontraktor_proposal" dengan fieldname sebenarnya dari console
					return doc.kontraktor_proposal || [];
				  })
				: Promise.resolve([]),
			frappe.xcall("sth.legal.doctype.bapp.bapp.get_unclaimed_pengeluaran_barang_items", {
				bapp: frm.doc.name,
			}),
		]).then(([contractor_rows, pb_items]) => {
			 console.log("contractor_rows:", contractor_rows);  // ← lihat di browser console
		console.log("proposal:", frm.doc.proposal);
			const contractors = contractor_rows.map(r => r.kontraktor);

			if (contractors.length <= 1) {
				// Tidak perlu pilih supplier, langsung ke step pengeluaran barang
				this._show_pb_and_create_pi(frm, null, pb_items);
			} else {
				// Step 2: pilih supplier dulu
				const dialog = new frappe.ui.Dialog({
					title: __("Pilih Supplier untuk Purchase Invoice"),
					fields: [
						{
							label: __("Supplier"),
							fieldname: "selected_supplier",
							fieldtype: "Link",
							options: "Supplier",
							reqd: 1,
							get_query: () => ({ filters: { name: ["in", contractors] } }),
							description: `${contractors.length} kontraktor tersedia. Qty akan dibagi rata (1/${contractors.length} per PI).`,
						},
					],
					primary_action_label: __("Lanjut"),
					primary_action: (values) => {
						dialog.hide();
						this._show_pb_and_create_pi(frm, values.selected_supplier, pb_items);
					},
				});
				dialog.show();
			}
		});
	}

	_show_pb_and_create_pi(frm, selected_supplier, pb_items) {
		const _call_make_pi = (selected_items) => {
			frappe.call({
				method: "sth.legal.doctype.bapp.bapp.make_purchase_invoice",
				args: {
					source_name: frm.doc.name,
					selected_supplier: selected_supplier || null,
					selected_items: selected_items || null,
				},
				callback(r) {
					if (r.message) {
						frappe.model.sync(r.message);
						frappe.set_route("Form", r.message.doctype, r.message.name);
					}
				},
			});
		};

		if (!pb_items || !pb_items.length) {
			// Tidak ada pengeluaran barang, langsung buat PI
			_call_make_pi(null);
			return;
		}

		// Tampilkan dialog pengeluaran barang
		const fmt = (val) => frappe.format(val, { fieldtype: "Currency" });
		const rows = pb_items.map((item, idx) => `
			<tr>
				<td class="text-center">
					<input type="checkbox" class="pb-item-check" data-idx="${idx}" checked />
				</td>
				<td>${item.kode_barang}</td>
				<td>${item.item_name}</td>
				<td class="text-right">${item.jumlah} ${item.satuan || ""}</td>
				<td class="text-right">${fmt(item.rate)}</td>
				<td class="text-right">${fmt(item.amount)}</td>
			</tr>`).join("");

		const d = new frappe.ui.Dialog({
			title: __("Pengeluaran Barang Belum Ditagihkan"),
			fields: [{
				fieldtype: "HTML",
				options: `
					<div style="overflow-x:auto">
						<table class="table table-bordered table-condensed" style="font-size:12px">
							<thead class="grid-heading-row">
								<tr>
									<th style="width:40px">
										<input type="checkbox" id="pb-check-all" checked />
									</th>
									<th>Kode Barang</th><th>Nama Barang</th>
									<th class="text-right">Qty</th>
									<th class="text-right">Rate</th>
									<th class="text-right">Amount</th>
								</tr>
							</thead>
							<tbody>${rows}</tbody>
						</table>
					</div>`,
			}],
			primary_action_label: __("Buat Purchase Invoice"),
			primary_action() {
				const selected_items = [];
				d.$wrapper.find(".pb-item-check:checked").each(function () {
					selected_items.push(pb_items[parseInt($(this).data("idx"))].name);
				});
				if (!selected_items.length) {
					frappe.msgprint(__("Pilih minimal satu item."));
					return;
				}
				d.hide();
				_call_make_pi(selected_items);
			},
			secondary_action_label: __("Lewati"),
			secondary_action() {
				d.hide();
				_call_make_pi(null);
			},
		});

		d.show();
		d.$wrapper.find("#pb-check-all").on("change", function () {
			d.$wrapper.find(".pb-item-check").prop("checked", this.checked);
		});
	}

	make_purchase_invoice() {
		this._make_pi_with_supplier_dialog(cur_frm);
	}

	close_bapp() {
		cur_frm.cscript.update_status("Closed");
	}

	reopen_bapp() {
		cur_frm.cscript.update_status("Submitted");
	}

	apply_putaway_rule() {
		if (this.frm.doc.apply_putaway_rule) erpnext.apply_putaway_rule(this.frm);
	}
};

// for backward compatibility: combine new and previous states
extend_cscript(cur_frm.cscript, new erpnext.stock.BAPPController({ frm: cur_frm }));

cur_frm.cscript.update_status = function (status) {
	frappe.ui.form.is_saving = true;
	frappe.call({
		method: "sth.legal.doctype.bapp.bapp.update_bapp_status",
		args: { docname: cur_frm.doc.name, status: status },
		callback: function (r) {
			if (!r.exc) cur_frm.reload_doc();
		},
		always: function () {
			frappe.ui.form.is_saving = false;
		},
	});
};

cur_frm.fields_dict["items"].grid.get_field("project").get_query = function (doc, cdt, cdn) {
	return {
		filters: [["Project", "status", "not in", "Completed, Cancelled"]],
	};
};

cur_frm.fields_dict["select_print_heading"].get_query = function (doc, cdt, cdn) {
	return {
		filters: [["Print Heading", "docstatus", "!=", "2"]],
	};
};

cur_frm.fields_dict["items"].grid.get_field("bom").get_query = function (doc, cdt, cdn) {
	var d = locals[cdt][cdn];
	return {
		filters: [
			["BOM", "item", "=", d.item_code],
			["BOM", "is_active", "=", "1"],
			["BOM", "docstatus", "=", "1"],
		],
	};
};

frappe.provide("erpnext.buying");