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

	onload(frm) {
		if (frm.is_new()) {
			new frappe.ui.Scanner({
				dialog: true,
				multiple: false,
				on_scan(data) {
					if (data && data.result && data.result.text) {
						frm.set_value("machine_station", data.result.text);
						frm.set_value("tanggal_scan", frappe.datetime.get_today())
						frm.set_value("jam_scan", moment().format('HH:mm:ss'))
						frm.set_value("user_scan", frappe.session.user)
					}
				},
			})
		}
	},

	machine_station(frm) {
		frm.set_query("machine", (doc) => {
			return {
				filters: {
					station: doc.machine_station
				}
			}
		})
	}

});

