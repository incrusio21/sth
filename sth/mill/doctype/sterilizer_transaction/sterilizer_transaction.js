// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sterilizer Transaction", {
	setup(frm) {
		frm.set_query("machine", (doc) => {
			return {
				filters: {
					station: doc.machine_station
				}
			}
		})
	},
	machine_station(frm) {
		frm.set_query("machine", (doc) => {
			return {
				filters: {
					station: doc.machine_station
				}
			}
		})
	},
});
