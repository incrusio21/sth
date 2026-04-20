// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Monitoring TBS Olah", {
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
	refresh: function (frm) {
		frm.get_field('table_vjjc').grid.cannot_delete_rows = true;
		frm.get_field('table_vjjc').grid.refresh();
	},
	validate: function (frm) {
		update_all(frm)
	}
});

frappe.ui.form.on('Thresing Detail', {
	table_vjjc_add: function (frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		const today = moment()
		const next_posting_date = frappe.datetime.add_days(cur_frm.doc.tgl, 1)
		const limit = moment(`${next_posting_date} 07:00:00`)

		if (today.isAfter(limit) && !frm.doc.skip_validation_tbs_olah) {
			frappe.model.clear_doc(row.doctype, row.name)
			refresh_field("table_vjjc")
			frappe.throw("Tidak bisa input tbs olah melebihi jam 7.")
		}

		frappe.model.set_value(cdt, cdn, 'jam', frappe.datetime.now_time());
		update_all(frm);
	},
	table_vjjc_remove: function (frm) {
		update_all(frm);
	}
});

function update_all(frm) {
	let rows = frm.doc.table_vjjc;
	let total_rows = rows.length;

	frm.set_value('tbs_olah', total_rows);

	if (total_rows >= 2) {
		let first_jam = rows[0].jam;
		let last_jam = rows[total_rows - 1].jam;

		if (first_jam && last_jam) {
			let first_time = frappe.datetime.str_to_obj('2000-01-01 ' + first_jam);
			let last_time = frappe.datetime.str_to_obj('2000-01-01 ' + last_jam);
			let diff_hours = (last_time - first_time) / (1000 * 60 * 60);
			frm.set_value('total_jam', diff_hours.toFixed(2));
		}
	} else {
		frm.set_value('total_jam', 0);
	}
}