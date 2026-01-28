// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.provide("sth.utils")

frappe.ui.form.on("Kalibrasi Timbangan Internal", {
	refresh(frm) {
		frm.add_custom_button(__("Connect"), function () {
			frm.trigger('readWeight')
		})
		
	},
	readWeight(frm) {
		frappe.scaleConnection = frappe.scaleConnection || new sth.utils.scale_connection();
		frappe.scaleConnection.connect().then(() => {
			frappe.scaleConnection.startReading((weight) => {
				if (weight.includes('kg')) {
					let weight_number = parseFloat(weight.split('kg')[0])
					frm.doc.live_weight = weight_number || 0
					frm.refresh_field("live_weight")
				}
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
