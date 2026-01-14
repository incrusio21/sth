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
                r.message.name = frm.docname
                frappe.model.sync(r.message);
                frm.refresh()
            },
        });
    },
});