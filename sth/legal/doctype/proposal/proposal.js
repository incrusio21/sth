// Copyright (c) 2026 DAS and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("erpnext.buying");
frappe.provide("erpnext.accounts.dimensions");

cur_frm.cscript.tax_table = "Purchase Taxes and Charges";

erpnext.accounts.taxes.setup_tax_filters("Purchase Taxes and Charges");
erpnext.accounts.taxes.setup_tax_validations("Proposal");
erpnext.buying.setup_buying_controller();

/**
 * Fungsi untuk membuka dialog update progress penerimaan barang
 * @param {Object} opts - Options berisi frm, child_doctype, dan child_docname
 */
erpnext.utils.update_progress_received = function (opts) {
	const frm = opts.frm;
	const child_meta = frappe.get_meta(opts.child_doctype);
	const get_precision = (fieldname) => child_meta.fields.find((f) => f.fieldname == fieldname).precision;

	// Siapkan data dari child table items
	this.data = frm.doc[opts.child_docname].map((d) => {
		return {
			docname: d.name,
			name: d.name,
			kegiatan: d.kegiatan,
			qty: d.qty,
			uom: d.uom,
			rate: d.rate,
			progress_received: d.progress_received
		};
	});

	// Konfigurasi field untuk dialog table
	const fields = [
		{
			fieldtype: "Data",
			fieldname: "docname",
			read_only: 1,
			hidden: 1,
		},
		{
			fieldtype: "Link",
			fieldname: "kegiatan",
			options: "Kegiatan",
			in_list_view: 1,
			read_only: 1,
			disabled: 0,
			columns: 5,
			label: __("Kegiatan")
		},
		{
			fieldtype: "Float",
			fieldname: "qty",
			in_list_view: 1,
			read_only: 1,
			columns: 1,
			label: __("Qty"),
		},
		{
			fieldtype: "Link",
			fieldname: "uom",
			options: "UOM",
			in_list_view: 1,
			read_only: 1,
			columns: 1,
			label: __("UOM"),
		},
		{
			fieldtype: "Currency",
			fieldname: "rate",
			options: "currency",
			default: 0,
			read_only: 1,
			in_list_view: 1,
			label: __("Rate"),
			precision: get_precision("rate"),
		},
		{
			fieldtype: "Float",
			fieldname: "progress_received",
			default: 0,
			read_only: 0,
			in_list_view: 1,
			columns: 1,
			label: __("Progress"),
			precision: get_precision("progress_received"),
		},
	];

	// Buat dan tampilkan dialog
	let dialog = new frappe.ui.Dialog({
		title: __("Update Progress"),
		size: "extra-large",
		fields: [
			{
				fieldname: "trans_items",
				fieldtype: "Table",
				label: "Items",
				cannot_add_rows: true,
				cannot_delete_rows: true,
				in_place_edit: false,
				reqd: 1,
				data: this.data,
				get_data: () => {
					return this.data;
				},
				fields: fields,
			},
		],
		primary_action: function () {
			// Kirim data ke server untuk update progress
			frappe.call({
				method: "sth.legal.doctype.proposal.proposal.update_progress_item",
				freeze: true,
				args: {
					parent_doctype: frm.doc.doctype,
					trans_items: this.get_values()["trans_items"],
					parent_doctype_name: frm.doc.name,
					child_docname: opts.child_docname,
				},
				callback: function () {
					frm.reload_doc();
				},
			});
			this.hide();
			refresh_field("items");
		},
		primary_action_label: __("Update"),
	});

	dialog.show();
};

frappe.ui.form.on("Proposal", {
	setup: function (frm) {
		frm.ignore_doctypes_on_cancel_all = ["Unreconcile Payment", "Unreconcile Payment Entries"];
		
		frm.set_indicator_formatter("item_code", function (doc) {
			let color;
			if (!doc.qty && frm.doc.has_unit_price_items) {
				color = "yellow";
			} else if (doc.qty <= doc.received_qty) {
				color = "green";
			} else {
				color = "orange";
			}
			return color;
		});

		frm.set_query("expense_account", "items", function () {
			return {
				query: "erpnext.controllers.queries.get_expense_account",
				filters: { company: frm.doc.company },
			};
		});

		frm.set_query("fg_item", "items", function () {
			return {
				filters: {
					is_stock_item: 1,
					is_sub_contracted_item: 1,
					default_bom: ["!=", ""],
				},
			};
		});
		
		frm.set_query("unit", function (doc) {
			return {
				filters: {
					company: ["=", doc.company],
				},
			};
		});

        frm.set_query("kegiatan", "items", function (doc) {
			return {
				filters: {
					is_group: 0,
				},
			};
		});

        frm.set_query("blok", "items", function (doc) {
			return {
				filters: {
					unit: ["=", doc.unit],
				},
			};
		});
	},

	company: function (frm) {
		erpnext.accounts.dimensions.update_dimension(frm, frm.doctype);
	},

	refresh: function (frm) {
		if (frm.doc.is_old_subcontracting_flow) {
			frm.trigger("get_materials_from_supplier");

			$("a.grey-link").each(function () {
				var id = $(this).children(":first-child").attr("data-label");
				if (id == "Duplicate") {
					$(this).remove();
					return false;
				}
			});
		}

		if (frm.doc.docstatus == 0) {
			erpnext.set_unit_price_items_note(frm);
		}
	},

	supplier: function (frm) {
		// Do not update if inter company reference is there as the details will already be updated
		if (frm.updating_party_details || frm.doc.inter_company_invoice_reference) return;

		if (frm.doc.__onload && frm.doc.__onload.load_after_mapping) return;

		erpnext.utils.get_party_details(
			frm,
			"erpnext.accounts.party.get_party_details",
			{
				posting_date: frm.doc.transaction_date,
				bill_date: frm.doc.bill_date,
				party: frm.doc.supplier,
				party_type: "Supplier",
				account: frm.doc.credit_to,
				price_list: frm.doc.buying_price_list,
				fetch_payment_terms_template: cint(!frm.doc.ignore_default_payment_terms_template),
			},
			function () {
				frm.set_df_property("apply_tds", "read_only", frm.supplier_tds ? 0 : 1);
				frm.set_df_property("tax_withholding_category", "hidden", frm.supplier_tds ? 0 : 1);
			}
		);
	},

	get_materials_from_supplier: function (frm) {
		let po_details = [];

		if (frm.doc.supplied_items && (flt(frm.doc.per_received) == 100 || frm.doc.status === "Closed")) {
			frm.doc.supplied_items.forEach((d) => {
				if (d.total_supplied_qty && d.total_supplied_qty != d.consumed_qty) {
					po_details.push(d.name);
				}
			});
		}

		if (po_details && po_details.length) {
			frm.add_custom_button(
				__("Return of Components"),
				() => {
					frm.call({
						method: "erpnext.controllers.subcontracting_controller.get_materials_from_supplier",
						freeze: true,
						freeze_message: __("Creating Stock Entry"),
						args: {
							subcontract_order: frm.doc.name,
							rm_details: po_details,
							order_doctype: cur_frm.doc.doctype,
						},
						callback: function (r) {
							if (r && r.message) {
								const doc = frappe.model.sync(r.message);
								frappe.set_route("Form", doc[0].doctype, doc[0].name);
							}
						},
					});
				},
				__("Create")
			);
		}
	},

	onload: function (frm) {
		set_schedule_date(frm);
		if (!frm.doc.transaction_date) {
			frm.set_value("transaction_date", frappe.datetime.get_today());
		}

		if (frm.doc.__onload && frm.doc.supplier) {
			if (frm.is_new()) {
				frm.doc.apply_tds = frm.doc.__onload.supplier_tds ? 1 : 0;
			}
			if (!frm.doc.__onload.supplier_tds) {
				frm.set_df_property("apply_tds", "read_only", 1);
			}
		}

		erpnext.queries.setup_queries(frm, "Warehouse", function () {
			return erpnext.queries.warehouse(frm.doc);
		});

		// On cancel and amending a Proposal with advance payment, reset advance paid amount
		if (frm.is_new()) {
			frm.set_value("advance_paid", 0);
		}
	},

	apply_tds: function (frm) {
		if (!frm.doc.apply_tds) {
			frm.set_value("tax_withholding_category", "");
		} else {
			frm.set_value("tax_withholding_category", frm.supplier_tds);
		}
	},

	get_subcontracting_boms_for_finished_goods: function (fg_item) {
		return frappe.call({
			method: "erpnext.subcontracting.doctype.subcontracting_bom.subcontracting_bom.get_subcontracting_boms_for_finished_goods",
			args: {
				fg_items: fg_item,
			},
		});
	},

	get_subcontracting_boms_for_service_item: function (service_item) {
		return frappe.call({
			method: "erpnext.subcontracting.doctype.subcontracting_bom.subcontracting_bom.get_subcontracting_boms_for_service_item",
			args: {
				service_item: service_item,
			},
		});
	},
});

frappe.ui.form.on("Proposal Item", {
	schedule_date: function (frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		if (row.schedule_date) {
			if (!frm.doc.schedule_date) {
				erpnext.utils.copy_value_in_all_rows(frm.doc, cdt, cdn, "items", "schedule_date");
			} else {
				set_schedule_date(frm);
			}
		}
	},

	kegiatan(frm, cdt, cdn){
        let item = locals[cdt][cdn]

        frappe.call({
            method: "sth.legal.doctype.proposal.proposal.get_kegiatan_item",
            args: {
                "kegiatan": item.kegiatan
            },
            callback: function (r) {
                frappe.model.set_value(cdt, cdn, r.message)
            }
        })
    },
});

erpnext.buying.ProposalController = class ProposalController extends (
	erpnext.buying.BuyingController
) {
	setup() {
		this.frm.custom_make_buttons = {
			"BAPP": "BAPP",
			"Purchase Invoice": "Purchase Invoice",
			"Payment Entry": "Payment",
		};

		frappe.flags.ignore_company_party_validation = true
		super.setup();
	}

	refresh(doc, cdt, cdn) {
		var me = this;
		super.refresh();
		var allow_receipt = false;
		var is_drop_ship = false;

		for (var i in cur_frm.doc.items) {
			var item = cur_frm.doc.items[i];
			if (item.delivered_by_supplier !== 1) {
				allow_receipt = true;
			} else {
				is_drop_ship = true;
			}

			if (is_drop_ship && allow_receipt) {
				break;
			}
		}

		this.frm.set_df_property("drop_ship", "hidden", !is_drop_ship);

		if (doc.docstatus == 1) {
			this.frm.fields_dict.items_section.wrapper.addClass("hide-border");
			if (!this.frm.doc.set_warehouse) {
				this.frm.fields_dict.items_section.wrapper.removeClass("hide-border");
			}

			if (!["Closed", "Delivered"].includes(doc.status)) {
				if (
					this.frm.doc.status !== "Closed" &&
					flt(this.frm.doc.per_received) < 100 &&
					flt(this.frm.doc.per_billed) < 100
				) {
					this.frm.add_custom_button(__("Update Progress"), () => {
						erpnext.utils.update_progress_received({
							frm: me.frm,
							child_docname: "items",
							child_doctype: "Proposal Item",
						});
					});

					this.frm.add_custom_button(
						__("Proposal Revision"), () => {
							frappe.model.open_mapped_doc({
								method: "sth.legal.doctype.proposal.proposal.make_proposal_revision",
								frm: me.frm,
								freeze_message: __("Creating Proposal Revision ..."),
							});
						},
						__("Create")
					);
				}
				if (this.frm.has_perm("submit")) {
					if (flt(doc.per_billed) < 100 || flt(doc.per_received) < 100) {
						if (doc.status != "On Hold") {
							this.frm.add_custom_button(
								__("Hold"),
								() => this.hold_purchase_order(),
								__("Status")
							);
						} else {
							this.frm.add_custom_button(
								__("Resume"),
								() => this.unhold_purchase_order(),
								__("Status")
							);
						}
						this.frm.add_custom_button(
							__("Close"),
							() => this.close_purchase_order(),
							__("Status")
						);
					}
				}

				if (is_drop_ship && doc.status != "Delivered") {
					this.frm.add_custom_button(
						__("Delivered"),
						this.delivered_by_supplier.bind(this),
						__("Status")
					);

					this.frm.page.set_inner_btn_group_as_primary(__("Status"));
				}
			} else if (["Closed", "Delivered"].includes(doc.status)) {
				if (this.frm.has_perm("submit")) {
					this.frm.add_custom_button(
						__("Re-open"),
						() => this.unclose_purchase_order(),
						__("Status")
					);
				}
			}
			if (doc.status != "Closed") {
				if (doc.status != "On Hold") {
					if (flt(doc.per_received) < 100 && allow_receipt) {
						this.frm.add_custom_button(
							__("BAPP"),
							this.make_bapp,
							__("Create")
						);
					}
					// // Please do not add precision in the below flt function
					// if (flt(doc.per_billed) < 100)
					// 	this.frm.add_custom_button(
					// 		__("Purchase Invoice"),
					// 		this.make_purchase_invoice,
					// 		__("Create")
					// 	);

					// if (flt(doc.per_billed) < 100 && doc.status != "Delivered") {
					// 	this.frm.add_custom_button(
					// 		__("Payment"),
					// 		() => this.make_payment_entry(),
					// 		__("Create")
					// 	);
					// }

					// if (flt(doc.per_billed) < 100) {
					// 	this.frm.add_custom_button(
					// 		__("Payment Request"),
					// 		function () {
					// 			me.make_payment_request();
					// 		},
					// 		__("Create")
					// 	);
					// }
				}

				cur_frm.page.set_inner_btn_group_as_primary(__("Create"));
			}
		} else if (doc.docstatus === 0) {
			cur_frm.cscript.add_from_mappers();
		}
	}

	get_items_from_open_material_requests() {
		erpnext.utils.map_current_doc({
			method: "erpnext.stock.doctype.material_request.material_request.make_purchase_order_based_on_supplier",
			args: {
				supplier: this.frm.doc.supplier,
			},
			source_doctype: "Material Request",
			source_name: this.frm.doc.supplier,
			target: this.frm,
			setters: {
				company: this.frm.doc.company,
			},
			get_query_filters: {
				docstatus: ["!=", 2],
				supplier: this.frm.doc.supplier,
			},
			get_query_method:
				"erpnext.stock.doctype.material_request.material_request.get_material_requests_based_on_supplier",
		});
	}
	
	validate() {
		set_schedule_date(this.frm);
	}
	
	has_unsupplied_items() {
		return this.frm.doc["supplied_items"].some((item) => item.required_qty > item.supplied_qty);
	}

	make_stock_entry() {
		frappe.call({
			method: "erpnext.controllers.subcontracting_controller.make_rm_stock_entry",
			args: {
				subcontract_order: cur_frm.doc.name,
				order_doctype: cur_frm.doc.doctype,
			},
			callback: function (r) {
				var doclist = frappe.model.sync(r.message);
				frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
			},
		});
	}

	make_bapp() {
		frappe.model.open_mapped_doc({
			method: "sth.legal.doctype.proposal.proposal.make_bapp",
			frm: cur_frm,
			freeze_message: __("Creating BAPP ..."),
		});
	}

	make_purchase_invoice() {
		frappe.model.open_mapped_doc({
			method: "erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_invoice",
			frm: cur_frm,
		});
	}

	add_from_mappers() {
		var me = this;
		this.frm.add_custom_button(
			__("Material Request"),
			function () {
				erpnext.utils.map_current_doc({
					method: "erpnext.stock.doctype.material_request.material_request.make_purchase_order",
					source_doctype: "Material Request",
					target: me.frm,
					setters: {
						schedule_date: undefined,
					},
					get_query_filters: {
						material_request_type: "Purchase",
						docstatus: 1,
						status: ["!=", "Stopped"],
						per_ordered: ["<", 100],
						company: me.frm.doc.company,
					},
					allow_child_item_selection: true,
					child_fieldname: "items",
					child_columns: ["item_code", "qty", "ordered_qty"],
				});
			},
			__("Get Items From")
		);

		this.frm.add_custom_button(
			__("Supplier Quotation"),
			function () {
				erpnext.utils.map_current_doc({
					method: "erpnext.buying.doctype.supplier_quotation.supplier_quotation.make_purchase_order",
					source_doctype: "Supplier Quotation",
					target: me.frm,
					setters: {
						supplier: me.frm.doc.supplier,
						valid_till: undefined,
					},
					get_query_filters: {
						docstatus: 1,
						status: ["not in", ["Stopped", "Expired"]],
					},
				});
			},
			__("Get Items From")
		);

		this.frm.add_custom_button(
			__("Link to Material Request"),
			function () {
				var my_items = [];
				for (var i in me.frm.doc.items) {
					if (!me.frm.doc.items[i].material_request) {
						my_items.push(me.frm.doc.items[i].item_code);
					}
				}
				frappe.call({
					method: "erpnext.buying.utils.get_linked_material_requests",
					args: {
						items: my_items,
					},
					callback: function (r) {
						if (r.exc) return;

						var i = 0;
						var item_length = me.frm.doc.items.length;
						while (i < item_length) {
							var qty = me.frm.doc.items[i].qty;
							(r.message[0] || []).forEach(function (d) {
								if (
									d.qty > 0 &&
									qty > 0 &&
									me.frm.doc.items[i].item_code == d.item_code &&
									!me.frm.doc.items[i].material_request_item
								) {
									me.frm.doc.items[i].material_request = d.mr_name;
									me.frm.doc.items[i].material_request_item = d.mr_item;
									var my_qty = Math.min(qty, d.qty);
									qty = qty - my_qty;
									d.qty = d.qty - my_qty;
									me.frm.doc.items[i].stock_qty =
										my_qty * me.frm.doc.items[i].conversion_factor;
									me.frm.doc.items[i].qty = my_qty;

									frappe.msgprint(
										"Assigning " +
											d.mr_name +
											" to " +
											d.item_code +
											" (row " +
											me.frm.doc.items[i].idx +
											")"
									);
									if (qty > 0) {
										frappe.msgprint("Splitting " + qty + " units of " + d.item_code);
										var new_row = frappe.model.add_child(
											me.frm.doc,
											me.frm.doc.items[i].doctype,
											"items"
										);
										item_length++;

										for (var key in me.frm.doc.items[i]) {
											new_row[key] = me.frm.doc.items[i][key];
										}

										new_row.idx = item_length;
										new_row["stock_qty"] = new_row.conversion_factor * qty;
										new_row["qty"] = qty;
										new_row["material_request"] = "";
										new_row["material_request_item"] = "";
									}
								}
							});
							i++;
						}
						refresh_field("items");
					},
				});
			},
			__("Tools")
		);
	}

	tc_name() {
		this.get_terms();
	}

	items_add(doc, cdt, cdn) {
		var row = frappe.get_doc(cdt, cdn);
		if (doc.schedule_date) {
			row.schedule_date = doc.schedule_date;
			refresh_field("schedule_date", cdn, "items");
		} else {
			this.frm.script_manager.copy_from_first_row("items", row, ["schedule_date"]);
		}
	}

	unhold_purchase_order() {
		cur_frm.cscript.update_status("Resume", "Draft");
	}

	hold_purchase_order() {
		var me = this;
		var d = new frappe.ui.Dialog({
			title: __("Reason for Hold"),
			fields: [
				{
					fieldname: "reason_for_hold",
					fieldtype: "Text",
					reqd: 1,
				},
			],
			primary_action: function () {
				var data = d.get_values();
				let reason_for_hold = "Reason for hold: " + data.reason_for_hold;

				frappe.call({
					method: "frappe.desk.form.utils.add_comment",
					args: {
						reference_doctype: me.frm.doctype,
						reference_name: me.frm.docname,
						content: __(reason_for_hold),
						comment_email: frappe.session.user,
						comment_by: frappe.session.user_fullname,
					},
					callback: function (r) {
						if (!r.exc) {
							me.update_status("Hold", "On Hold");
							d.hide();
						}
					},
				});
			},
		});
		d.show();
	}

	unclose_purchase_order() {
		cur_frm.cscript.update_status("Re-open", "Submitted");
	}

	close_purchase_order() {
		cur_frm.cscript.update_status("Close", "Closed");
	}

	delivered_by_supplier() {
		cur_frm.cscript.update_status("Deliver", "Delivered");
	}

	items_on_form_rendered() {
		set_schedule_date(this.frm);
	}

	schedule_date() {
		set_schedule_date(this.frm);
	}
};

// for backward compatibility: combine new and previous states
extend_cscript(cur_frm.cscript, new erpnext.buying.ProposalController({ frm: cur_frm }));

cur_frm.cscript.update_status = function (label, status) {
	frappe.call({
		method: "erpnext.buying.doctype.purchase_order.purchase_order.update_status",
		args: { status: status, name: cur_frm.doc.name },
		callback: function (r) {
			cur_frm.set_value("status", status);
			cur_frm.reload_doc();
		},
	});
};

cur_frm.fields_dict["items"].grid.get_field("project").get_query = function (doc, cdt, cdn) {
	return {
		filters: [["Project", "status", "not in", "Completed, Cancelled"]],
	};
};

if (cur_frm.doc.is_old_subcontracting_flow) {
	cur_frm.fields_dict["items"].grid.get_field("bom").get_query = function (doc, cdt, cdn) {
		var d = locals[cdt][cdn];
		return {
			filters: [
				["BOM", "item", "=", d.item_code],
				["BOM", "is_active", "=", "1"],
				["BOM", "docstatus", "=", "1"],
				["BOM", "company", "=", doc.company],
			],
		};
	};
}

function set_schedule_date(frm) {
	if (frm.doc.schedule_date) {
		erpnext.utils.copy_value_in_all_rows(
			frm.doc,
			frm.doc.doctype,
			frm.doc.name,
			"items",
			"schedule_date"
		);
	}
}

frappe.provide("erpnext.buying");
