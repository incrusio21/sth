// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Rencana Kerja Harian Pemeliharaan Mesin-Mesin", {
	refresh(frm) {
		if(frm.doc.lokasi_kerja){
			frm.set_query("jenis_mesin_yang_diperbaiki", function () {
				return {
					filters: {
						station: ["=", frm.doc.lokasi_kerja]
					}
				};
			});
		}	
	},
	lokasi_kerja(frm){
		if(frm.doc.lokasi_kerja){
			frm.set_query("jenis_mesin_yang_diperbaiki", function () {
				return {
					filters: {
						station: ["=", frm.doc.lokasi_kerja]
					}
				};
			});
		}	
	}
});
