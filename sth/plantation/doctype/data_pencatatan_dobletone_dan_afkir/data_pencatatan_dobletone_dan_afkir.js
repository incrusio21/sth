// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Data Pencatatan Dobletone Dan Afkir", {
	setup(frm) {

		frm.set_query("batch", function() {
			return {
				query: "sth.api.get_batch_penyemaian"
			};
		});

	},
	data_penyemaian_bibit(frm) {

		if (!frm.doc.data_penyemaian_bibit) {
			frm.set_value("available_qty", 0);
			return;
		}

		frappe.call({
			method: "sth.plantation.doctype.data_pencatatan_dobletone_dan_afkir.data_pencatatan_dobletone_dan_afkir.get_available_qty",
			args: {
				data_penyemaian_bibit: frm.doc.data_penyemaian_bibit
			},
			callback(r) {

				if (r.message) {
					frm.set_value(
						"available_qty",
						r.message
					);
				}

			}
		});

	},
	onload: function(frm) {      
		if (frm.is_new() && !frm.doc.posting_time) {
			let now = frappe.datetime.now_time(); 
			frm.set_value("posting_time", now);
		}
	},
	refresh(frm) {
		frm.set_query("data_penyemaian_bibit", function(doc) {
			return {
				"filters": [
					["company",  "=", doc.company],
					["docstatus",  "=", 1],                    
				]
			};            
		});
	},
	batch(frm) {

		if (!frm.doc.batch) {
			frm.set_value("data_penyemaian_bibit", "");
			return;
		}

		frappe.db.get_value(
			"Data Penyemaian Bibit",
			{
				batch: frm.doc.batch,
				docstatus: 1
			},
			"name"
		).then(r => {

			if (r.message && r.message.name) {

				frm.set_value(
					"data_penyemaian_bibit",
					r.message.name
				);

			} else {

				frm.set_value(
					"data_penyemaian_bibit",
					""
				);

				frappe.msgprint(
					"Data Penyemaian Bibit untuk batch ini tidak ditemukan."
				);
			}

		});

	}
	,qty(frm){
		if(frm.doc.qty>frm.doc.available_qty){
			frm.set_value("qty", frm.doc.available_qty);
			frappe.msgprint("Jumlah Bibit must not be greater than " + frm.doc.available_qty);
		}else if(frm.doc.qty<0){
			frm.set_value("qty", frm.doc.available_qty);
			frappe.msgprint("Jumlah Bibit must not be less than 0");
		}
	}
});