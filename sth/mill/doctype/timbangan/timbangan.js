// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt
frappe.provide("sth.utils")

frappe.ui.form.on("Timbangan", {
	setup(frm) {
		frm.set_query("spb", (doc) => {
			return {
				query: frappe.model.get_server_module_name(doc.doctype) + ".get_spb_available"
			}
		})
	},

	refresh(frm) {
		frm.ignore_doctypes_on_cancel_all = ["TBS Ledger Entry"]

		// buat tombol untuk create transaksi
		make_transaction_button(frm)

		if (frm.doc.docstatus == 1) return

		navigator.serial.getPorts().then((port) => {
			if (!port.length || !localStorage.getItem('location')) {
				frm.trigger('selectLocationDialog')
			} else {
				frm.events.readWeight(frm, localStorage.getItem('location'), port[0])
			}

		});

		set_field_visibility(frm)
	},

	receive_type(frm) {
		if (frm.doc.receive_type == "TBS Internal" || frm.doc.receive_type == "TBS Eksternal") {
			frm.set_value("kode_barang", "TBS")
		}
	},

	selectLocationDialog(frm) {
		const method = frappe.model.get_server_module_name(frm.doctype) + '.get_timbangan_settings'
		frappe.xcall(method).then((res) => {
			const locations = res.map((d) => d.location)
			let dialog = new frappe.ui.Dialog({
				title: "Select Location",
				fields: [{
					label: "Lokasi Timbangan",
					fieldname: "location",
					fieldtype: "Select",
					options: locations.join("\n"),
					reqd: 1
				}],
				primary_action_label: "Connect",
				primary_action(values) {
					dialog.hide()
					frm.events.readWeight(frm, values.location)
				}
			})

			dialog.show()
		})

	},

	readWeight(frm, location = "", port = null) {
		console.log(location);
		frappe.scaleConnection = new sth.utils.scale_connection(location, port);
		if (location) {
			localStorage.setItem('location', location)
		}
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

		frappe
			.xcall("frappe.client.get_value", {
				doctype: "Security Check Point",
				filters: {
					spb: frm.doc.spb
				},
				fieldname: ["name"],
			})
			.then((res) => {
				frm.set_value("ticket_number", res.name)
			})
	},

	no_segel(frm) {
		frm.set_value("jumlah_segel", frm.doc.no_segel.length)
	},

	reference_do_item(frm) {
		if (!frm.doc.reference_do_item) return
		const method = frappe.model.get_server_module_name(frm.doctype) + ".get_sisa_do"
		frappe.xcall(method, { reference: frm.doc.reference_do_item })
			.then((r) => {
				frm.set_value("sisa_do", r)
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
		frappe.run_serially([
			() => frm.trigger('calculate_weight'),
			() => frm.set_value("jumlah_janjang", frm.doc.netto / frm.doc.isi_komidel)
		])
	},

	type(frm) {
		set_field_visibility(frm)
	},

	after_save(frm) {
		set_field_visibility(frm)
	},

	calculate_weight(frm) {
		frm.set_value("netto", frm.doc.bruto - frm.doc.tara)
		frm.set_value("netto_2", frm.doc.bruto - frm.doc.tara - ((frm.doc.bruto - frm.doc.tara) * frm.doc.potongan_sortasi / 100))
	},
	potongan_sortasi(frm) {
		frm.trigger('calculate_weight')
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
			// frm.add_custom_button(__('Create Delivery Note'), function () {
			// 	frappe.call({
			// 		method: 'sth.mill.doctype.timbangan.timbangan.make_delivery_note',
			// 		args: {
			// 			source_name: frm.doc.name
			// 		},
			// 		callback: function (r) {
			// 			if (r.message) {
			// 				// Buka form DN baru tanpa save
			// 				frappe.model.sync(r.message);
			// 				frappe.set_route('Form', r.message.doctype, r.message.name);
			// 			}
			// 		}
			// 	});
			// }, __('Create'));
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

// frappe.form.link_formatters['Item'] = function (value, doc) {
// 	console.log(value);
// 	return value
// }