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