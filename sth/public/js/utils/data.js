// Copyright (c) 2025, DAS and Contributors
// MIT License. See license.txt

frappe.provide("sth.form");

sth.form = {
    doctype_setting: {},
    
    reset_value: function (frm, fields=[]) {
        if(!Array.isArray(fields)){
            fields = [fields]
        }
        
        // menghitung amount, rotasi, qty
        for (const fieldname of fields) {
            frm.doc[fieldname] = undefined
        }

        frm.refresh_fields()
	},
    setup_fieldname_select: function (frm, field_grid) {
        let me = this
        frm.fields_dict[field_grid].grid.setup_user_defined_columns = function() {
            if (!this.frm) return;
            
            let user_settings = me.doctype_setting[this.frm.doctype] || frappe.get_user_settings(this.frm.doctype, "GridView");
            if (user_settings && user_settings[this.doctype] && user_settings[this.doctype].length) {
                this.user_defined_columns = user_settings[this.doctype]
                    .map((row) => {
                        let column = frappe.meta.get_docfield(this.doctype, row.fieldname);

                        if (column) {
                            column.in_list_view = 1;
                            column.columns = row.columns;
                            return column;
                        }
                    })
                    .filter(Boolean);
            }
        }
    }
}