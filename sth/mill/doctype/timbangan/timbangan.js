// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt
frappe.provide("sth.utils")

frappe.ui.form.on("Timbangan", {
	refresh(frm) {
		frm.ignore_doctypes_on_cancel_all = ["TBS Ledger Entry"]
		frm.add_custom_button(__("Connect"), function () {
			frm.trigger('readWeight')
		})

		// buat tombol untuk create transaksi
		make_transaction_button(frm)
		set_field_visibility(frm)
	},

	receive_type(frm) {
		if (frm.doc.receive_type == "TBS Internal" || frm.doc.receive_type == "TBS Eksternal") {
			frm.set_value("kode_barang", "TBS")
		}
	},

	readWeight(frm) {
		frappe.scaleConnection = frappe.scaleConnection || new sth.utils.scale_connection();
		frappe.scaleConnection.connect().then(() => {
			frappe.scaleConnection.startReading((weight) => {
				const match = weight.match(/([+-]?\d+)\s*kg/i);
				const weight_number = match ? Number(match[1]) : null;
				frm.doc.live_weight = weight_number || 0
				frm.refresh_field("live_weight")

				// if (weight.includes('kg')) {
				// 	let weight_number = parseFloat(weight.split('kg')[0])
				// 	frm.doc.live_weight = weight_number || 0
				// 	frm.refresh_field("live_weight")
				// }
			});
		})
	},

	spb(frm) {
		frm.clear_table('spb_detail')
		if (!frm.doc.spb) {
			return
		}
		const base = frappe.model.get_server_module_name(frm.doctype)
		frappe.xcall(`${base}.get_spb_detail`, { spb: frm.doc.spb })
			.then((res) => {
				res.forEach(row => {
					frm.add_child('spb_detail', row)
				});
				frm.refresh_field('spb_detail')
			})
	},

	gateweight(frm) {
		if (!frm.doc.docstatus == 0) {
			return
		}

		frm.set_value("bruto", frm.doc.live_weight)
		frm.set_value("weight_out_time", frappe.datetime.now_time())
	},

	gateweight2(frm) {
		if (!frm.doc.docstatus == 0) {
			return
		}

		frm.set_value("tara", frm.doc.live_weight)
		frm.set_value("weight_out_time", frappe.datetime.now_time())
	},

	bruto(frm) {
		frm.trigger('calculate_weight')
	},

	tara(frm) {
		frm.trigger('calculate_weight')
	},

	type(frm) {
		set_field_visibility(frm)
	},

	after_save(frm) {
		set_field_visibility(frm)
	},

	calculate_weight(frm) {
		frm.set_value("netto", frm.doc.bruto - frm.doc.tara - (frm.doc.potongan_sortasi / 100))
	}
})




window.addEventListener("beforeunload", () => {
	if (frappe.scaleConnection) {
		frappe.scaleConnection.close();
	}
});


function make_transaction_button(frm) {
	// Tampilkan button hanya jika belum ada reference
	if (!frm.doc.reference_name && !frm.is_new() && frm.doc.docstatus == 1) {
		if (frm.doc.type == "Dispatch") {
			frm.add_custom_button(__('Create Delivery Note'), function () {
				frappe.call({
					method: 'sth.mill.doctype.timbangan.timbangan.make_delivery_note',
					args: {
						source_name: frm.doc.name
					},
					callback: function (r) {
						if (r.message) {
							// Buka form DN baru tanpa save
							frappe.model.sync(r.message);
							frappe.set_route('Form', r.message.doctype, r.message.name);
						}
					}
				});
			}, __('Create'));
		}

		if (frm.doc.type == "Receive") {
			frm.add_custom_button(__('Create Purchase Receipt'), function () {
				frappe.call({
					method: 'sth.mill.doctype.timbangan.timbangan.make_purchase_receipt',
					args: {
						source_name: frm.doc.name
					},
					callback: function (r) {
						if (r.message) {
							// Buka form PR baru tanpa save
							frappe.model.sync(r.message);
							frappe.set_route('Form', r.message.doctype, r.message.name);
						}
					}
				});
			}, __('Create'));
		}
	}
}

function set_field_visibility(frm) {
	if (frm.is_new()) {
		if (frm.doc.type == "Dispatch") {
			frm.set_df_property('bruto', 'hidden', 1);
			frm.set_df_property('gateweight', 'hidden', 1);
			frm.set_df_property('tara', 'hidden', 0);
			frm.set_df_property('gateweight2', 'hidden', 0);
			frm.set_df_property('netto', 'hidden', 1);
		}
		else if (frm.doc.type == "Receive" || frm.doc.type == "Return") {
			frm.set_df_property('tara', 'hidden', 1);
			frm.set_df_property('gateweight2', 'hidden', 1);
			frm.set_df_property('bruto', 'hidden', 0);
			frm.set_df_property('gateweight', 'hidden', 0);
			frm.set_df_property('netto', 'hidden', 1);
		}
		else {
			frm.set_df_property('bruto', 'hidden', 1);
			frm.set_df_property('gateweight', 'hidden', 1);
			frm.set_df_property('tara', 'hidden', 1);
			frm.set_df_property('gateweight2', 'hidden', 1);
			frm.set_df_property('netto', 'hidden', 1);
		}

	}
	else {
		// When saved document
		if (frm.doc.type == "Dispatch" && frm.doc.tara) {
			frm.set_df_property('bruto', 'hidden', 0);
			frm.set_df_property('gateweight', 'hidden', 0);
			frm.set_df_property('tara', 'hidden', 0);
			frm.set_df_property('gateweight2', 'hidden', 0);
			frm.set_df_property('netto', 'hidden', 0);
		}
		else if (frm.doc.type == "Dispatch") {
			frm.set_df_property('bruto', 'hidden', 1);
			frm.set_df_property('gateweight', 'hidden', 1);
			frm.set_df_property('tara', 'hidden', 0);
			frm.set_df_property('gateweight2', 'hidden', 0);
			frm.set_df_property('netto', 'hidden', 1);
		}

		else if ((frm.doc.type == "Receive" || frm.doc.type === "Return") && frm.doc.bruto) {
			frm.set_df_property('bruto', 'hidden', 0);
			frm.set_df_property('gateweight', 'hidden', 0);
			frm.set_df_property('tara', 'hidden', 0);
			frm.set_df_property('gateweight2', 'hidden', 0);
			frm.set_df_property('netto', 'hidden', 0);
		}
		else if (frm.doc.type == "Receive" || frm.doc.type === "Return") {
			frm.set_df_property('bruto', 'hidden', 0);
			frm.set_df_property('gateweight', 'hidden', 0);
			frm.set_df_property('tara', 'hidden', 1);
			frm.set_df_property('gateweight2', 'hidden', 1);
			frm.set_df_property('netto', 'hidden', 1);
		}
	}
}