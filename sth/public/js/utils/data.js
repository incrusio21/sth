// Copyright (c) 2025, DAS and Contributors
// MIT License. See license.txt

frappe.provide("sth.form");

sth.form = {
    doctype_setting: {},
    purchase_type_column: {},
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
            
            let user_settings = frappe.get_user_settings(this.frm.doctype, "GridView") 
            if(!Object.keys(user_settings).length){
                user_settings = me.doctype_setting[this.frm.doctype];
            }
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
    },
    setup_column_table_items: async function(frm, purchase_type, doctype_table, fields="items"){
        // Simpan konfigurasi doctype lama untuk perbandingan
        const old_doctype_setting = this.doctype_setting[frm.doctype] || {};

        // Ambil konfigurasi kolom dari cache atau API jika belum ada
        if (purchase_type && !this.purchase_type_column[purchase_type]) {
            // get list visible column berdasarkan order type
            this.purchase_type_column[purchase_type] = (
                await frappe.call(
                    "sth.buying_sth.doctype.purchase_type.purchase_type.get_order_type_configure_column",
                    {
                        order_type: purchase_type,
                    }
                )
            ).message;
        }

        // Buat konfigurasi baru berdasarkan order_type
        const new_doctype_setting = this.purchase_type_column[purchase_type]?.length > 0 
        ? { [doctype_table]: this.purchase_type_column[purchase_type] }
        : {};

        // Update grid jika konfigurasi berubah
        const has_changed = JSON.stringify(old_doctype_setting) !== JSON.stringify(new_doctype_setting);
        if (has_changed) {
            console.log("tesa")
            this.doctype_setting[frm.doctype] = new_doctype_setting;
            frm.fields_dict[fields].grid.reset_grid();
        }
    }
}