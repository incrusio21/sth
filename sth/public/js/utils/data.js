// Copyright (c) 2025, DAS and Contributors
// MIT License. See license.txt

frappe.provide("sth.form");

sth.form = {
    reset_value: function (frm, fields=[]) {
        if(!Array.isArray(fields)){
            fields = [fields]
        }
        
        // menghitung amount, rotasi, qty
        for (const fieldname of fields) {
            frm.doc[fieldname] = undefined
        }

        frm.refresh_fields()
	}
}