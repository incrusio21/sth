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
        frm.set_df_property("net_total", "hidden", 1)
    },

    validate(frm) {
        if (frm.doc.docstatus != 0) return

        // Kumpulkan unique purchase_order dari items
        const po_names = [...new Set(
            (frm.doc.items || [])
                .map((d) => d.purchase_order)
                .filter(Boolean)
        )]

        if (!po_names.length) return

        frm.clear_table('taxes')

        // Fetch taxes dari setiap PO lalu copy ke PR
        const promises = po_names.map((po_name) =>
            frappe.xcall('frappe.client.get', {
                doctype: 'Purchase Order',
                name: po_name,
                filters: { name: po_name }
            }).then((po) => {
                for (const tax of (po.taxes || [])) {
                    // Cek apakah account_head sudah ada (hindari duplikat jika multi-PO)
                    const exists = (frm.doc.taxes || []).find(
                        (t) => t.account_head === tax.account_head
                    )
                    if (exists) continue

                    const row = frm.add_child('taxes')
                    row.account_head    = tax.account_head
                    row.charge_type     = tax.charge_type
                    row.add_deduct_tax  = tax.add_deduct_tax
                    row.tax_amount      = tax.tax_amount
                    row.description     = tax.description
                    row.tipe_pajak      = tax.tipe_pajak
                    row.category        = tax.category
                }
            })
        )

        return Promise.all(promises).then(() => {
            frm.refresh_field('taxes')
        })
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
        frm.set_df_property("net_total", "hidden", 1)
        frm.set_query("set_warehouse", function (doc) {
            return {
                query: "sth.controllers.queries.get_wh_prec",
                filters: {
                    company: doc.company,
                    unit: doc.unit
                }
            };
        });
        if(frm.doc.docstatus == 1){
            frm.page.remove_inner_button(__('Purchase Invoice'), __('Create'));
            frm.add_custom_button(__('Purchase Invoice'), () => {
                frappe.model.open_mapped_doc({
                    method: "sth.overrides.purchase_receipt.make_purchase_invoice",
                    frm: cur_frm,
                });
            }, __('Create'));
        }

        
    },

    make_purchase_invoice() {
        frappe.model.open_mapped_doc({
            method: "sth.overrides.purchase_receipt.make_purchase_invoice",
            frm: cur_frm,
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
            method: "sth.buying_sth.custom.purchase_order.make_purchase_receipt",
            args: {
                source_name: frm.doc.purchase_order,
            },
            freeze: true,
            freeze_message: "Mapping Data...",
            debounce: 1000,
            callback: function (r) {
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