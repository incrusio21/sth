// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt


/**
 * Fungsi untuk membuka dialog update progress penerimaan barang
 * @param {Object} opts - Options berisi frm, child_doctype, dan child_docname
 */
erpnext.utils.update_progress_received = function (opts) {
	const frm = opts.frm;
	const child_meta = frappe.get_meta(opts.child_doctype);
	const benchmark_fieldname = frm.doc.__onload.progress_benchmark || "item_code"
	const benchmark_field = child_meta.fields.find((f) => f.fieldname == benchmark_fieldname)
	const get_precision = (fieldname) => child_meta.fields.find((f) => f.fieldname == fieldname).precision;

	// Siapkan data dari child table items
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

	// Konfigurasi field untuk dialog table
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

frappe.ui.form.on("Purchase Order", {
	setup(frm) {
		sth.form.setup_fieldname_select(frm, "items")
		// sth.form.override_class_function(frm.cscript, "calculate_totals", () => {
		// 	frm.trigger("set_value_dpp_and_taxes")
		// })
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

	company(frm) {
		frm.trigger('get_tax_template')
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

	total_biaya_ongkos_angkut(frm) {
		if (frappe.refererence.__ref_tax["Ongkos Angkut"]) {
			let coa = frappe.refererence.__ref_tax["Ongkos Angkut"].account
			let tax = frm.doc.taxes.find((r) => r.account_head == coa)
			if (tax) {
				frappe.model.set_value(tax.doctype, tax.name, "tax_amount", frm.doc.total_biaya_ongkos_angkut)
				frm.trigger('calculate_taxes_and_totals')
			}
		}
	},

	is_pph_22(frm) {
		if (!frm.doc.is_pph_22) {
			frm.set_value('pph_22', 0)
		}
	},

	pph_22(frm) {
		if (frappe.refererence.__ref_tax["PPH 22"]) {
			let coa = frappe.refererence.__ref_tax["PPH 22"].account
			let tax = frm.doc.taxes.find((r) => r.account_head == coa)
			if (tax) {
				frappe.model.set_value(tax.doctype, tax.name, "tax_amount", frm.doc.pph_22)
				frm.trigger('calculate_taxes_and_totals')
			}
		}
	},

	pbbkb(frm) {
		if (frappe.refererence.__ref_tax["PBBKB"]) {
			let coa = frappe.refererence.__ref_tax["PBBKB"].account
			let tax = frm.doc.taxes.find((r) => r.account_head == coa)
			if (tax) {
				frappe.model.set_value(tax.doctype, tax.name, "tax_amount", frm.doc.pbbkb)
				frm.trigger('calculate_taxes_and_totals')
			}
		}
	},

	get_tax_template(frm) {
		frappe.provide('frappe.refererence.__ref_tax')
		if (Object.keys(frappe.refererence.__ref_tax).length === 0) {
			if (!frm.doc.company) {
				return
			}

			frappe.xcall("sth.custom.supplier_quotation.get_taxes_template", { "company": frm.doc.company }).then((res) => {
				for (const row of res) {
					let taxes = frm.add_child('taxes')
					taxes.account_head = row.account
					taxes.add_deduct_tax = "Add"
					taxes.charge_type = "Actual"
					frm.script_manager.trigger(taxes.doctype, taxes.name, "account_head")
					frappe.refererence.__ref_tax[row.type] = row
				}
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

	set_value_dpp_and_taxes(frm) {
		frm.doc.dpp = frm.doc.net_total

		let total_ppn = 0
		let total_pph = 0
		let total_lainnya = 0
		for (const row of frm.doc.taxes) {
			if (row.tipe_pajak == "PPN") {
				total_ppn += row.tax_amount
			}
			else if (row.tipe_pajak == "PPH") {
				total_pph += row.tax_amount
			}
			else {
				total_lainnya += row.tax_amount
			}
		}
		// frm.doc.pph = frm.doc.taxes_and_charges_deducted
		// for (const row of frm.doc.taxes) {
		// 	if (row.account_head == frm._default_coa.ppn) {
		// 		frm.doc.ppn = row.tax_amount
		// 	}
		// }

		frm.doc.ppn = total_ppn
		frm.doc.pph = total_pph
		// frm.doc.biaya_lainnya = frm.doc.taxes_and_charges_added - frm.doc.ppn
		frm.doc.biaya_lainnya = total_lainnya
		frm.refresh_fields()
	},
});

frappe.ui.form.on("VAT Detail", {
	pph_lainnya_add(frm, dt, dn) {
		let row = locals[dt][dn]
		const tax = frm.add_child("taxes")
		tax.add_deduct_tax = "Add"
		tax.charge_type = "Actual"

		frappe.model.set_value(dt, dn, {
			"ref_child_doc": tax.doctype,
			"ref_child_name": tax.name,
			"tax_type": "PPH"
		})

	},

	ppn_add(frm, dt, dn) {
		let row = locals[dt][dn]
		const tax = frm.add_child("taxes")
		tax.add_deduct_tax = "Add"
		tax.charge_type = "Actual"

		frappe.model.set_value(dt, dn, {
			"ref_child_doc": tax.doctype,
			"ref_child_name": tax.name,
			"tax_type": "PPN"
		})

	},

	type(frm, dt, dn) {
		let row = locals[dt][dn]

		if (!frm.doc.company) {
			frappe.throw("Silahkan isi company lebih dahulu")
		}
		frappe.xcall("sth.custom.supplier_quotation.get_account_tax_rate", { name: row.type, company: frm.doc.company }).then((res) => {
			frappe.model.set_value(row.ref_child_doc, row.ref_child_name, "account_head", res)
			frm.script_manager.trigger(row.ref_child_doc, row.ref_child_name, "account_head")
		})
	},

	before_pph_lainnya_remove(frm, dt, dn) {
		let row = locals[dt][dn]
		frappe.model.clear_doc(row.ref_child_doc, row.ref_child_name)
	},

	percentage(frm, dt, dn) {
		let row = locals[dt][dn]
		const amount = frm.doc.total * row.percentage / 100

		frappe.model.set_value(row.ref_child_doc, row.ref_child_name, "tax_amount", amount)
		frappe.model.set_value(dt, dn, "amount", amount)
		frm.trigger('calculate_total_pph_lainnya')
		frm.trigger('calculate_taxes_and_totals')
	}
})