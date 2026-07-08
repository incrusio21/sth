// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt


erpnext.utils.update_progress_received = function (opts) {
	const frm = opts.frm;
	const child_meta = frappe.get_meta(opts.child_doctype);
	const benchmark_fieldname = frm.doc.__onload.progress_benchmark || "item_code"
	const benchmark_field = child_meta.fields.find((f) => f.fieldname == benchmark_fieldname)
	const get_precision = (fieldname) => child_meta.fields.find((f) => f.fieldname == fieldname).precision;

	this.data = frm.doc[opts.child_docname].map((d) => {
		return {
			docname: d.name,
			name: d.name,
			[benchmark_fieldname]: d[benchmark_fieldname],
			qty: d.qty,
			uom: d.uom,
			rate: d.rate,
			progress_received: d.progress_received
		};
	});

	const fields = [
		{
			fieldtype: "Data",
			fieldname: "docname",
			read_only: 1,
			hidden: 1,
		},
		{
			fieldtype: benchmark_field.fieldtype,
			fieldname: benchmark_field.fieldname,
			options: benchmark_field.options,
			in_list_view: 1,
			read_only: 1,
			disabled: 0,
			columns: 5,
			label: __(benchmark_field.label)
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
			frappe.call({
				method: "sth.buying_sth.custom.purchase_order.update_progress_item",
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


erpnext.buying.PurchaseOrderControllerCustom = class PurchaseOrderController extends (
	erpnext.buying.BuyingController
) {
	setup() {
		this.frm.custom_make_buttons = {
			"Purchase Receipt": "Purchase Receipt",
			"Purchase Invoice": "Purchase Invoice",
			"Payment Entry": "Payment",
			"Subcontracting Order": "Subcontracting Order",
			"Stock Entry": "Material to Supplier",
		};

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
					if (!this.frm.doc.__onload || this.frm.doc.__onload.can_update_items) {
						this.frm.add_custom_button(__("Update Items"), () => {
							erpnext.utils.update_child_items({
								frm: this.frm,
								child_docname: "items",
								child_doctype: "Purchase Order Detail",
								cannot_add_row: false,
							});
						});
					}
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
							__("Closes"),
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
							__("Purchase Receipt"),
							this.make_purchase_receipt,
							__("Create")
						);
						if (doc.is_subcontracted) {
							if (doc.is_old_subcontracting_flow) {
								if (me.has_unsupplied_items()) {
									cur_frm.add_custom_button(
										__("Material to Supplier"),
										function () {
											me.make_stock_entry();
										},
										__("Transfer")
									);
								}
							} else {
								if (!doc.items.every((item) => item.qty == item.subcontracted_quantity)) {
									this.frm.add_custom_button(
										__("Subcontracting Order"),
										() => {
											me.make_subcontracting_order();
										},
										__("Create")
									);
								}
							}
						}
					}
					if (flt(doc.per_billed) < 100)
						this.frm.add_custom_button(
							__("Purchase Invoice"),
							this.make_purchase_invoice,
							__("Create")
						);

					if (flt(doc.per_billed) < 100 && doc.status != "Delivered") {
						this.frm.add_custom_button(
							__("Payment"),
							() => this.make_payment_entry(),
							__("Create")
						);
					}

					if (flt(doc.per_billed) < 100) {
						this.frm.add_custom_button(
							__("Payment Request"),
							function () {
								me.make_payment_request();
							},
							__("Create")
						);
					}

					if (doc.docstatus === 1 && !doc.inter_company_order_reference) {
						let me = this;
						let internal = me.frm.doc.is_internal_supplier;
						if (internal) {
							let button_label =
								me.frm.doc.company === me.frm.doc.represents_company
									? "Internal Sales Order"
									: "Inter Company Sales Order";

							me.frm.add_custom_button(
								button_label,
								function () {
									me.make_inter_company_order(me.frm);
								},
								__("Create")
							);
						}
					}
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

	make_inter_company_order(frm) {
		frappe.model.open_mapped_doc({
			method: "erpnext.buying.doctype.purchase_order.purchase_order.make_inter_company_sales_order",
			frm: frm,
		});
	}

	make_purchase_receipt() {
		frappe.model.open_mapped_doc({
			method: "erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_receipt",
			frm: cur_frm,
			freeze_message: __("Creating Purchase Receipt ..."),
		});
	}

	make_purchase_invoice() {
		frappe.model.open_mapped_doc({
			method: "erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_invoice",
			frm: cur_frm,
		});
	}

	make_subcontracting_order() {
		frappe.model.open_mapped_doc({
			method: "erpnext.buying.doctype.purchase_order.purchase_order.make_subcontracting_order",
			frm: cur_frm,
			freeze_message: __("Creating Subcontracting Order ..."),
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
			__("Update Rate as per Last Purchase"),
			function () {
				frappe.call({
					method: "get_last_purchase_rate",
					doc: me.frm.doc,
					callback: function (r, rt) {
						me.frm.dirty();
						me.frm.cscript.calculate_taxes_and_totals();
					},
				});
			},
			__("Tools")
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
		frappe.call({
			method: 'sth.buying_sth.custom.purchase_order.check_uang_muka_payment_entry',
			args: {
				purchase_order: cur_frm.doc.name
			},
			callback: function (r) {
				if (r.message && r.message.has_payment_entry) {
					frappe.throw(
						'This Purchase Order has a GL Entry for Uang Muka with Payment Entry. Purchase Order cannot be closed.',
					)
				} else {
					cur_frm.cscript.update_status("Close", "Closed");
				}
			}
		});
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

extend_cscript(cur_frm.cscript, new erpnext.buying.PurchaseOrderControllerCustom({ frm: cur_frm }));


frappe.ui.form.on("Purchase Order", {
	setup(frm) {
		sth.form.setup_fieldname_select(frm, "items")
		frm.set_query("lokasi_pengiriman", function (doc) {
			return {
				filters: {
					company: doc.company
				}
			}
		})

		frm.set_query("type", "pph_lainnya", function (doc) {
			return {
				filters: {
					name: ["like", "%PPh%"]
				}
			}
		})

		frm.set_query("type", "ppn", function (doc) {
			return {
				filters: {
					name: ["like", "%PPN%"]
				}
			}
		})
	},

	refresh(frm) {
		frm.trigger('get_tax_template')
		frm.page.sidebar.hide()
		frm.set_query("purchase_type", () => {
			return {
				filters: {
					document_type: frm.doctype
				}
			}
		})

		frm.trigger("set_query_field")
		sth.form.setup_column_table_items(frm, frm.doc.purchase_type, "Purchase Order Item")
	},

	onload_post_render(frm) {
		frm.page.inner_toolbar.find(`div[data-label="${encodeURIComponent('Get Items From')}"]`).remove()
	},

	purchase_type(frm) {
		sth.form.setup_column_table_items(frm, frm.doc.purchase_type, "Purchase Order Item")
	},

	set_query_field(frm) {
		if (frm.doc.docstatus == 1 && !["Closed", "Delivered"].includes(frm.doc.status)) {
			if (
				frm.doc.status !== "Closed" &&
				flt(frm.doc.per_received) < 100 &&
				flt(frm.doc.per_billed) < 100 &&
				frm.doc.__onload.check_progress
			) {
				frm.add_custom_button(__("Update Progress"), () => {
					erpnext.utils.update_progress_received({
						frm: frm,
						child_docname: "items",
						child_doctype: "Purchase Order Item",
					});
				});
			}
		}
	},

	validate(frm) {
		if (frm.doc.docstatus == 0) {
			sync_to_taxes(frm)
		}
	},

	company(frm) {
		frm.trigger('get_tax_template')
	},

	waktu_penyerahan(frm) {
		const day = frm.doc.waktu_penyerahan ? frm.doc.waktu_penyerahan.split(' ')[0] : 0
		frm.set_value('accept_day', parseInt(day))
	},

	ppn_biaya_ongkos(frm) {
		frm.trigger('calculate_total_biaya_angkut')
	},

	is_ppn_ongkos(frm) {
		if (!frm.doc.is_ppn_ongkos) {
			frm.doc.ppn_biaya_ongkos = 0
		}
		frm.trigger('calculate_total_biaya_angkut')
	},

	biaya_ongkos(frm) {
		frm.trigger('calculate_total_biaya_angkut')
	},

	total_biaya_ongkos_angkut(frm) { sync_to_taxes(frm) },
	pph_22(frm) { sync_to_taxes(frm) },
	pbbkb(frm) { sync_to_taxes(frm) },
	cost(frm) { sync_to_taxes(frm) },

	is_pph_22(frm) {
		if (!frm.doc.is_pph_22) frm.set_value('pph_22', 0)
	},

	get_tax_template(frm) {
		frappe.provide('frappe.refererence.__ref_tax')
		if (Object.keys(frappe.refererence.__ref_tax).length === 0 && frm.doc.docstatus == 0) {
			if (!frm.doc.company) return

			frappe.xcall("sth.custom.supplier_quotation.get_taxes_template", { "company": frm.doc.company }).then((res) => {
				for (const row of res) {
					frappe.refererence.__ref_tax[row.type] = row
				}
				sync_to_taxes(frm)
			})
		}
	},

	calculate_total_biaya_angkut(frm) {
		const ppn_biaya = frm.doc.ppn_biaya_ongkos
		const is_ppn = frm.doc.is_ppn_ongkos
		const biaya_ongkos = is_ppn ? (ppn_biaya / 100 * frm.doc.biaya_ongkos) + frm.doc.biaya_ongkos : frm.doc.biaya_ongkos
		frm.set_value("total_biaya_ongkos_angkut", biaya_ongkos)
	},

	calculate_total_pph_lainnya(frm) {
		let total = 0
		for (const row of frm.doc.pph_lainnya) {
			total += row.amount
		}
		frm.set_value("total_pph_lainnya", total)
	},

	calculate_total_ppn(frm) {
		let total = 0
		for (const row of frm.doc.ppn) {
			total += row.amount
		}
		frm.set_value("total_ppn", total)
	},

	set_value_dpp_and_taxes(frm) {
		frm.doc.dpp = frm.doc.net_total

		let total_ppn = 0
		let total_pph = 0
		let total_lainnya = 0
		for (const row of frm.doc.taxes) {
			if (row.tipe_pajak == "PPN") {
				total_ppn += row.tax_amount
			} else if (row.tipe_pajak == "PPH") {
				total_pph += row.tax_amount
			} else {
				total_lainnya += row.tax_amount
			}
		}

		frm.doc.ppn = total_ppn
		frm.doc.pph = total_pph
		frm.doc.biaya_lainnya = total_lainnya
		frm.refresh_fields()
	},
});


frappe.ui.form.on("VAT Detail", {
	pph_lainnya_add(frm, dt, dn) {
		sync_to_taxes(frm)
	},

	ppn_add(frm, dt, dn) {
		sync_to_taxes(frm)
	},

	ph_lainnya_remove(frm, dt, dn) {
        sync_to_taxes(frm);
        frm.trigger('calculate_total_pph_lainnya')
        frm.trigger('calculate_total_ppn')
        frm.trigger('calculate_taxes_and_totals')
    },

    ppn_remove(frm, dt, dn) {
        sync_to_taxes(frm);
        frm.trigger('calculate_total_pph_lainnya')
        frm.trigger('calculate_total_ppn')
        frm.trigger('calculate_taxes_and_totals')
    },

	type(frm, dt, dn) {
        let row = locals[dt][dn]
        if (!frm.doc.company) {
            frappe.throw("Silahkan isi company lebih dahulu")
        }
        const tipe = row.parentfield == "ppn" ? "Masukan" : "PPh"
        frappe.xcall("sth.custom.supplier_quotation.get_account_tax_rate", { name: row.type, company: frm.doc.company, tipe: tipe }).then((res) => {
            frappe.model.set_value(dt, dn, "account", res)
            if(tipe == "PPh"){
                row.tax_type= "PPH"
            }
            else{
                row.tax_type="PPN"
            }
            frm.refresh_field(row.parentfield)
            sync_to_taxes(frm)
        })
    },


	amount(frm, dt, dn) {
		let row = locals[dt][dn]
		if (!row.ref_child_doc || !row.ref_child_name) return
		frappe.model.set_value(row.ref_child_doc, row.ref_child_name, "tax_amount", row.amount || 0)
		frm.trigger('calculate_total_pph_lainnya')
		frm.trigger('calculate_total_ppn')
		sync_to_taxes(frm)
	},

	percentage(frm, dt, dn) {
		let row = locals[dt][dn]
		const base = frm.doc.total || 0
		const amount = base * (row.percentage || 0) / 100

		frappe.model.set_value(row.ref_child_doc, row.ref_child_name, "tax_amount", amount)
		frappe.model.set_value(dt, dn, "amount", amount)
		frm.trigger('calculate_total_pph_lainnya')
		frm.trigger('calculate_total_ppn')
		sync_to_taxes(frm)
	}
});


// ─── Sync Taxes ──────────────────────────────────────────────────────────────

const PO_FIELD_MAP = [
    { key: "Ongkos Angkut", marker: "__ongkos_angkut__", field: "total_biaya_ongkos_angkut" },
    { key: "PPH 22",        marker: "__pph_22__",         field: "pph_22" },
    { key: "PBBKB",         marker: "__pbbkb__",          field: "pbbkb" },
    { key: "Cost",          marker: "__cost__",            field: "cost" },
]

const CHARGES_MARKER = "__from_charges__";
const PB_MARKER = "__from_pb__";

function sync_to_taxes(frm){
    frm.doc.taxes = []
    sync_diskon_to_taxes(frm, true)
    sync_ppn_to_taxes(frm, true)
    sync_all_to_taxes(frm)

    frm.refresh_field("taxes");
    frm.trigger("calculate_taxes_and_totals");
}

function sync_ppn_to_taxes(frm, skip_recalc = false) {
    const PPN_MARKER = "__from_ppn__";

    for (const row of (frm.doc.ppn || [])) {
        if (!row.amount || !row.type) continue;

        let tax = frm.add_child("taxes");
        tax.account_head = row.account
        tax.charge_type = "Actual";
        tax.add_deduct_tax = "Add";
        tax.category = "Total";
        tax.tax_amount = row.amount || 0;
        tax.description = `${PPN_MARKER}${row.type || ""}`;
    }

    frm.refresh_field("taxes");
    frm.trigger("calculate_taxes_and_totals");
}

function sync_diskon_to_taxes(frm, skip_recalc = false) {

    const DISKON_MARKER = "__diskon__"

    // bersihkan row diskon lama dulu
    frm.doc.taxes = (frm.doc.taxes || []).filter(
        row => !(row.description || "").startsWith(DISKON_MARKER)
    )

    const jumlah_diskon = frm.doc.jumlah_diskon || 0
    const diskon_account = frm._diskon_account
    if (jumlah_diskon && diskon_account) {
        let diskon_row = frm.add_child("taxes")
        diskon_row.charge_type = "Actual"
        diskon_row.category = "Total"
        diskon_row.account_head = diskon_account
        diskon_row.tax_amount = -jumlah_diskon
        diskon_row.add_deduct_tax = "Add"
        diskon_row.description = DISKON_MARKER
    }
}

function sync_all_to_taxes(frm) {
    const ref_tax = frappe.refererence.__ref_tax || {}
    const field_map = [
        { key: "Ongkos Angkut", value: frm.doc.total_biaya_ongkos_angkut, add_deduct: "Add" },
        { key: "PPH 22",        value: frm.doc.pph_22,                     add_deduct: "Add" },
        { key: "PBBKB",         value: frm.doc.pbbkb,                      add_deduct: "Add" },
        { key: "Cost",          value: frm.doc.cost,                        add_deduct: "Add" },
    ]

    for (const { key, value, add_deduct } of field_map) {
        const ref = ref_tax[key]
        if (!ref) continue

        let tax = (frm.doc.taxes || []).find(r => r.account_head == ref.account)
        if (!tax) {
            tax = frm.add_child("taxes")
            tax.account_head = ref.account
            tax.charge_type = "Actual"
            tax.add_deduct_tax = add_deduct
            tax.category = "Total"
        }
        frappe.model.set_value(tax.doctype, tax.name, "tax_amount", value || 0)
    }
}

function calculate_sub_total(frm) {
    let sub_total = 0;
    if (frm.doc.voucher_type === "Non Voucher Match") {
        sub_total = (frm.doc.non_voucher_match || []).reduce((sum, r) => sum + (r.total || 0), 0);
    } else {
        const total_items = (frm.doc.items || []).reduce((sum, r) => sum + (r.amount || 0), 0);
        const total_charges = (frm.doc.charges_purchase_invoice || []).reduce((sum, r) => sum + (r.total || 0), 0);
        const total_pb = (frm.doc.purchase_invoice_pengeluaran_barang || []).reduce((sum, r) => sum + (r.amount || 0), 0);
        sub_total = total_items + total_charges - total_pb;
    }
    frm.set_value("sub_total", sub_total);
}

frappe.form.link_formatters['Item'] = function (value, doc) {
	return value
}
