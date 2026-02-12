frappe.provide("sth.queries")
frappe.provide("sth.form")
frappe.ui.form.on("Material Request", {
    setup(frm) {
        sth.form.override_class_function(frm.cscript, "refresh", () => {
            frm.page.inner_toolbar.find(`div[data-label="${encodeURIComponent('Get Items From')}"]`).remove()
            if (frm.doc.docstatus == 0) {
                frm.add_custom_button("Berita Acara", function () {
                    frm.trigger('get_berita_acara')
                }, __("Get Items From"))
            }
        })
    },

    onload: function (frm) {
        if (frm.doc.docstatus == 0) {
            frm.doc.items.forEach(function (item) {
                get_stock_for_item(frm, item.doctype, item.name);
            });
        }
    },


    refresh(frm) {
        if (frm.is_new()) {
            frm.trigger('set_default_reqdate')
        }

        sth.form.override_class_function(frm.cscript, "onload", () => {
            frm.set_query("item_code", "items", sth.queries.item_by_subtype)
        })

        frm.set_query("divisi", sth.queries.divisi)
        frm.trigger('refresh_read_only_fields')

    },

    unit(frm) {
        frm.trigger('set_unit_to_child')
    },

    set_default_reqdate(frm) {
        const required_date = frappe.datetime.add_days(frm.doc.date, 7)
        frm.set_value("schedule_date", required_date)
    },

    set_unit_to_child(frm) {
        frm.doc.items.forEach((row) => {
            row.unit = frm.doc.unit
        })
        refresh_field("items")
    },

    refresh_read_only_fields(frm) {
        const fields = ["material_request_type", "purchase_type", "sub_purchase_type", "company", "unit", "schedule_date", ["items", "item_code"], ["items", "qty"], ["items", "uom"], ["items", "kendaraan"]]

        for (const field of fields) {
            if (typeof field == "string") {
                frm.set_df_property(field, "read_only", frm.doc.__load_after_mapping || false)
            } else {
                frm.get_field(field[0]).grid.update_docfield_property(field[1], 'read_only', frm.doc.__load_after_mapping || false)
            }
        }
    },



    get_berita_acara(frm) {
        const d = new frappe.ui.Dialog({
            title: 'Get Items From Berita Acara',
            fields: [
                {
                    label: 'Berita Acara',
                    fieldname: 'berita_acara',
                    fieldtype: 'Link',
                    options: "Berita Acara",
                    get_query: function () {
                        return {
                            query: "sth.controllers.queries.get_berita_acara"
                        }
                    },
                    reqd: 1
                },
            ],
            primary_action_label: 'Get Items',
            primary_action(values) {
                frappe.xcall("sth.procurement_sth.doctype.berita_acara.berita_acara.create_mr", {
                    source_name: values.berita_acara,
                    freeze: true,
                    freeze_message: "Getting Items..."
                }).then((res) => {
                    frm.set_value({
                        "unit": res["unit"],
                        "company": res.company,
                        "sub_purchase_type": res["sub_purchase_type"],
                        "purchase_type": res["purchase_type"]
                    })

                    frm.clear_table("items")
                    for (const data of res.items) {
                        frm.add_child("items", data)
                        // get_stock_for_item(frm, child_item.doctype, child_item.name)
                    }
                    frm.doc.__load_after_mapping = 1
                    frm.refresh()
                })

                d.hide();
            }
        })
        d.show()
    },

});

frappe.ui.form.on("Material Request Item", {
    item_code(frm, dt, dn) {
        let row = locals[dt][dn]
        let exist = frm.doc.items.find((data) => row.item_code == data.item_code && row.idx != data.idx)
        if (exist) {
            frappe.msgprint("Item code sudah terdaftar dalam tabel.")
            frappe.model.clear_doc(row.doctype, row.name)
            refresh_field("items")
        }
        get_stock_for_item(frm, dt, dn);
    }
})

function get_stock_for_item(frm, cdt, cdn) {
    let row = locals[cdt][cdn];

    if (!row.item_code) {
        return;
    }

    let company = frm.doc.company;

    if (!company) {
        return;
    }

    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Warehouse',
            filters: {
                'company': company,
                'unit': frm.doc.unit,
                'central': 1
            },
            fields: ['name']
        },
        callback: function (r) {
            console.log(r);

            if (r.message && r.message.length > 0) {
                let warehouses = r.message.map(w => w.name);

                frappe.call({
                    method: 'erpnext.stock.utils.get_latest_stock_qty',
                    args: {
                        item_code: row.item_code,
                        warehouse: warehouses.length === 1 ? warehouses[0] : null
                    },
                    callback: function (stock_response) {
                        frappe.model.set_value(cdt, cdn, 'stock', stock_response.message || 0);
                    }
                });
            } else {
                frappe.model.set_value(cdt, cdn, 'stock', 0);
                frappe.msgprint(__('No central warehouse found for company {0}', [company]));
            }
        }
    });
}

frappe.form.link_formatters['Item'] = function (value, doc) {
    return doc.item_name || doc.item_code
}
