// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Pemeriksaan Temperatur Tangki- Tangki", {
// 	refresh(frm) {

// 	},
// });



frappe.ui.form.on("Pemeriksaan Temperatur Tangki- Tangki", {

    temperatur_cot: function(frm) {
        check_temp(frm, "temperatur_cot");
    },

    temperatur_pot: function(frm) {
        check_temp(frm, "temperatur_pot");
    },

    temperatur_cst: function(frm) {
        check_temp(frm, "temperatur_cst");
    },

    temperatur_stt: function(frm) {
        check_temp(frm, "temperatur_stt");
    },

    temperatur_st: function(frm) {
        check_temp(frm, "temperatur_st");
    }

});


function check_temp(frm, fieldname) {

    let value = frm.doc[fieldname];

    if (!value) return;

    frappe.db.get_single_value("Mill Settings", fieldname).then((standard) => {

        if (!standard) return;

        let selisih = value - standard;

        let info_field = fieldname + "_info";

        if (selisih > 0) {
            frm.set_value(info_field, selisih + "° Diatas Standard");
        } 
        else if (selisih < 0) {
            frm.set_value(info_field, Math.abs(selisih) + "° Dibawah Standard");
        } 
        else {
            frm.set_value(info_field, "");
        }

    });

}