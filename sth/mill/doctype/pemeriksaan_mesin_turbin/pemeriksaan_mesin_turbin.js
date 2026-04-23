// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pemeriksaan Mesin Turbin", {
	onload(frm) {
		if (frm.is_new()) {
			new frappe.ui.Scanner({
				dialog: true,
				multiple: false,
				on_scan(data) {
					if (data && data.result && data.result.text) {
						frm.set_value("stasiun", data.result.text);
						frm.set_value("tanggal_scan", frappe.datetime.get_today())
						frm.set_value("jam_scan", moment().format('HH:mm:ss'))
						frm.set_value("user_scan", frappe.session.user)
					}
				},
			})
		}
	},
	refresh(frm) {

	},
	hm_awal_turbin(frm) {
		hitung_hm(frm)
	},
	hm_akhir_turbin(frm) {
		hitung_hm(frm)
	},
});

function hitung_hm(frm) {
	frm.set_value("total_hm_turbin", frm.doc.hm_akhir_turbin - frm.doc.hm_awal_turbin)
}
