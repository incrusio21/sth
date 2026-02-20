// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.provide("sth.utils")

frappe.ui.form.on("Kalibrasi Timbangan Internal", {
	refresh(frm) {
		navigator.serial.getPorts().then((port) => {
			if (!port.length || !localStorage.getItem('location')) {
				frm.trigger('selectLocationDialog')
			} else {
				frm.events.readWeight(frm, localStorage.getItem('location'))
			}

		});

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

	readWeight(frm, location = "") {
		console.log(location);
		frappe.scaleConnection = new sth.utils.scale_connection(location);
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

	gateweight(frm) {
		if (!frm.doc.docstatus == 0) {
			return
		}
		frm.set_value("beban_berat_1", frm.doc.live_weight)
	},

	gateweight2(frm) {
		if (!frm.doc.docstatus == 0) {
			return
		}
		frm.set_value("beban_berat_2", frm.doc.live_weight)
	},
	gateweight3(frm) {
		if (!frm.doc.docstatus == 0) {
			return
		}
		frm.set_value("beban_berat_3", frm.doc.live_weight)
	},
	gateweight4(frm) {
		if (!frm.doc.docstatus == 0) {
			return
		}
		frm.set_value("beban_berat_4", frm.doc.live_weight)
	},
	gateweight5(frm) {
		if (!frm.doc.docstatus == 0) {
			return
		}
		frm.set_value("beban_berat_5", frm.doc.live_weight)
	},
	gateweight6(frm) {
		if (!frm.doc.docstatus == 0) {
			return
		}
		frm.set_value("beban_berat_6", frm.doc.live_weight)
	},
});
