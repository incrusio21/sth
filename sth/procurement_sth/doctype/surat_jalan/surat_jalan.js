// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Surat Jalan", {
    setup(frm) {
        const wh_fields = ["gudang_tujuan", "gudang_asal"]
        wh_fields.forEach(field => {
            frm.set_query(field, function (doc) {
                return {
                    filters: {
                        is_group: 0,
                        company: doc.company
                    }
                }
            })
        });

        frm.set_query("unit", function (doc) {
            return {
                filters: {
                    company: doc.company
                }
            }
        })
    },

    refresh(frm) {
        if (frm.doc.docstatus == 0) {
            frm.add_custom_button("Purchase Order", function () {
                frm.events.open_dialog_get_items(frm, "purchase")
            }, __("Get Items From"))

            frm.add_custom_button("Material", function () {
                frm.events.open_dialog_get_items(frm, "material")
            }, __("Get Items From"))
        }
    },

    open_dialog_get_items(frm, type) {
        const base = frappe.model.get_server_module_name(frm.doctype)
        let method = base + ".get_items_from_po"
        if (type == "material") {
            const d = new frappe.ui.Dialog({
                title: "Select Material",
                size: "large",
                fields: [
                    {
                        label: "Kode Barang",
                        fieldname: "item_code",
                        fieldtype: "Link",
                        options: "Item",
                        onchange: function () {
                            if (!d.get_field("warehouse").get_value()) {
                                frappe.throw("Silahkan isi gudang terlebih dahulu")
                            }
                        }
                    },
                    {
                        fieldname: "column_breaks_1",
                        fieldtype: "Column Break",
                    },
                    {
                        label: "Gudang",
                        fieldname: "warehouse",
                        fieldtype: "Link",
                        options: "Warehouse",
                        reqd: 1,
                        get_query: function () {
                            return {
                                filters: {
                                    is_group: 0,
                                    company: frm.doc.company
                                }
                            }

                        }
                    },
                    {
                        fieldname: "section_breaks_1",
                        fieldtype: "Section Break",
                    },
                    {
                        label: "Items",
                        fieldname: "items",
                        fieldtype: "Table",
                        in_place_edit: true,
                        reqd: 1,
                        fields: [
                            {
                                label: "Kode Barang",
                                fieldname: "item_code",
                                fieldtype: "Link",
                                options: "Item",
                                read_only: 1,
                                in_list_view: 1,
                                columns: 3
                            },
                            {
                                label: "Nama Barang",
                                fieldname: "item_name",
                                fieldtype: "Data",
                                read_only: 1,
                                in_list_view: 1,
                                columns: 3
                            },
                            {
                                label: "Qty",
                                fieldname: "qty",
                                fieldtype: "Float",
                                in_list_view: 1,
                                columns: 2
                            },
                            {
                                label: "Stock Gudang",
                                fieldname: "stock",
                                fieldtype: "Float",
                                in_list_view: 1,
                                read_only: 1,
                                columns: 2
                            },

                        ]
                    },
                ],
                primary_action_label: 'Get Items',
                primary_action(values) {
                    console.log(values);
                    d.hide();
                }
            })

            d.set_df_property("items", "cannot_add_rows", 1)
            d.show()
        }

    }
});
