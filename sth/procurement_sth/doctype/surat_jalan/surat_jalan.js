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
                frm.trigger('open_dialog_po')
            }, __("Get Items From"))

            frm.add_custom_button("Material", function () {
                frm.trigger('open_dialog_material')
            }, __("Get Items From"))
        }
    },

    open_dialog_material(frm) {
        const base = frappe.model.get_server_module_name(frm.doctype)
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
                        const item_code = this.value
                        const warehouse = d.get_field("warehouse").get_value()
                        const old_items = d.get_field("items").get_value()
                        if (!warehouse) {
                            frappe.throw("Silahkan isi gudang terlebih dahulu")
                        }

                        if (!item_code) {
                            return
                        }

                        frappe.xcall(base + ".get_stock_item", { item_code, warehouse })
                            .then((res) => {
                                console.log(res);

                                // cek apakah sudah ada item code yang sama sebelumnya
                                if (res) {
                                    const is_exist_before = old_items.some(r => r.item_code == res[0].item_code)

                                    if (is_exist_before) {
                                        return
                                    }
                                }

                                d.get_field("items").df.data = [...old_items, ...res]
                                d.get_field("items").refresh()

                            })

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
                            columns: 2
                        },
                        {
                            label: "Nama Barang",
                            fieldname: "item_name",
                            fieldtype: "Data",
                            read_only: 1,
                            in_list_view: 1,
                            columns: 2
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

                        {
                            label: "Satuan",
                            fieldname: "uom",
                            fieldtype: "Link",
                            options: "UOM",
                            in_list_view: 1,
                            columns: 2
                        },

                    ]
                },
            ],
            primary_action_label: 'Get Items',
            primary_action(values) {
                values.items.forEach((row) => {
                    frm.add_child("items", {
                        kode_barang: row.item_code,
                        nama_barang: row.item_name,
                        jumlah: row.qty,
                        satuan: row.uom
                    })
                    frm.refresh_field('items')
                })

                d.hide();
            }
        })

        d.set_df_property("items", "cannot_add_rows", 1)
        d.show()
    },

    open_dialog_po(frm) {
        const base = frappe.model.get_server_module_name(frm.doctype)
        const d = erpnext.utils.map_current_doc({
            method: base + ".map_from_po",
            source_doctype: "Purchase Order",
            target: frm,
            allow_child_item_selection: 1,
            child_fieldname: "items",
            child_columns: ["item_code", "item_name", "qty", "uom"],
            size: "extra-large",
            setters: {
                purchase_type: undefined,
                unit: undefined,
                transaction_date: undefined,
            },
            get_query_filters: {
                docstatus: 1,
                company: frm.doc.company,
            },
        }, (res) => {
            console.log(res);
        });

        setTimeout(() => {
            // console.log(d.dialog);
            d.dialog.set_value("allow_child_item_selection", 1)
        }, 500);
    }
});
