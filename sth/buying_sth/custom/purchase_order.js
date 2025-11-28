// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Order", {
    setup(frm){
        frm.order_type_column = {}
        sth.form.setup_fieldname_select(frm, "items")
    },
    refresh(frm){
        frm.trigger("setup_column_table_items");
    },
    order_type(frm){
        frm.trigger("setup_column_table_items");
    },
    async setup_column_table_items(frm){
        // Simpan konfigurasi doctype lama untuk perbandingan
        const old_doctype_setting = sth.form.doctype_setting[frm.doctype] || {};

        // Ambil konfigurasi kolom dari cache atau API jika belum ada
        if (frm.doc.order_type && !frm.order_type_column[frm.doc.order_type]) {
            // get list visible column berdasarkan order type
            frm.order_type_column[frm.doc.order_type] = (
                await frappe.call(
                    "sth.buying_sth.custom.purchase_order.get_order_type_configure_column",
                    {
                        order_type: frm.doc.order_type,
                    }
                )
            ).message;
        }

        // Buat konfigurasi baru berdasarkan order_type
        const column_config = frm.order_type_column[frm.doc.order_type];
        const new_doctype_setting = column_config?.length > 0 
        ? { "Purchase Order Item": column_config }
        : {};

        // Update grid jika konfigurasi berubah
        const has_changed = JSON.stringify(old_doctype_setting) !== JSON.stringify(new_doctype_setting);
        if (has_changed) {
            sth.form.doctype_setting[frm.doctype] = new_doctype_setting;
            frm.fields_dict["items"].grid.reset_grid();
        }
    }
});