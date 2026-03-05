// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Receipt", {
    setup(frm) {
        sth.form.setup_fieldname_select(frm, "items")

        frm.set_query("purchase_order", (doc) => {
            return {
                filters: {
                    docstatus: 1,
                    per_received: ["<", 100],
                    unit: doc.unit,
                    company: doc.company,
                    supplier: doc.supplier
                }
            }
        })

        frm.set_query("unit", function (doc) {
            return {
                filters: {
                    company: ["=", doc.company],
                },
            };
        });

        frm.set_query("bank_account", function (doc) {
            return {
                filters: {
                    unit: ["=", doc.unit],
                },
            };
        });
    },

    onload(frm) {
        if (frm.is_new()) {
            frm.clear_table("upload")
            const files = ["FOTO BARANG", "SURAT JALAN"]
            files.forEach((r) => {
                frm.add_child("upload", {
                    rincian_dokumen_finance: r
                })
            })
        }
    },

    refresh(frm) {
        frm.set_query("purchase_type", () => {
            return {
                filters: {
                    document_type: frm.doctype
                }
            }
        })
        sth.form.setup_column_table_items(frm, frm.doc.purchase_type, null, "Purchase Type")
        frm.remove_custom_button("Purchase Invoice", "Get Items From")
        sth.form.override_class_function(frm.cscript, 'refresh', () => {
            frm.remove_custom_button("Purchase Order", "Get Items From")
        })
        frm.remove_custom_button("Purchase Order", "Get Items From")
        console.log("Masuk");

        frm.set_query("set_warehouse", function (doc) {
            return {
                query: "sth.controllers.queries.get_wh_prec",
                filters: {
                    company: doc.company,
                    unit: doc.unit
                }
            };
        });
    },
    purchase_type(frm) {
        sth.form.setup_column_table_items(frm, frm.doc.purchase_type, null, "Purchase Type")
    },

    purchase_order(frm) {
        if (!frm.doc.purchase_order) {
            return
        }

        frappe.call({
            method: "erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_receipt",
            args: {
                source_name: frm.doc.purchase_order,
            },
            freeze: true,
            freeze_message: "Mapping Data...",
            debounce: 1000,
            callback: function (r) {
                console.log(frm.docname);

                r.message.name = frm.docname
                r.message.items = r.message.items.map((r) => { return { ...r, parent: frm.docname } })
                frappe.model.sync(r.message);
                frm.refresh()
            },
        });
    },
});


frappe.form.link_formatters['Item'] = function (value, doc) {
    return value
}
