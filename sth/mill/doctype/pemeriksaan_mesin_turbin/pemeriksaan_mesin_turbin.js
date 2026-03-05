// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pemeriksaan Mesin Turbin", {
	refresh(frm) {

	},
	hm_awal_turbin(frm){
		hitung_hm(frm)
	},
	hm_akhir_turbin(frm){
		hitung_hm(frm)
	},
});

function hitung_hm(frm){
	frm.set_value("total_hm_turbin", frm.doc.hm_akhir_turbin - frm.doc.hm_awal_turbin)
}
