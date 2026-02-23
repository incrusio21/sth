// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("CBC Monitoring", {
	refresh(frm) {

	},
	starting_hour_meter(frm){
		hitung_total(frm)
	},
	ending_hour_meter(frm){
		hitung_total(frm)
	},
	setup(frm) {
		frm.set_query("cbc_machine", (doc) => {
			return {
				filters: {
					station: doc.machine_station
				}
			}
		})
	},
	machine_station(frm) {
		frm.set_query("cbc_machine", (doc) => {
			return {
				filters: {
					station: doc.machine_station
				}
			}
		})
	},
});

function hitung_total(frm){
	if(frm.doc.starting_hour_meter && frm.doc.ending_hour_meter){
		frm.set_value("total_hour_meter", frm.doc.ending_hour_meter - frm.doc.starting_hour_meter)
	}
}
