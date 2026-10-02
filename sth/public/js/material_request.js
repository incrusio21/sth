frappe.provide("sth.queries")
frappe.provide("sth.form")

// Tampilan link title (title field) untuk Item dimatikan selama berada di Material Request,
// supaya item_code tampil sebagai kode item, bukan item_name.
// frappe.utils bersifat global dan desk tidak reload saat pindah menu, jadi fungsi
// aslinya disimpan lalu dikembalikan begitu route keluar dari doctype ini.
const MR_DOCTYPE = "Material Request";
// Kosongkan untuk semua doctype.
const MR_HIDE_LINK_TITLE_FOR = ["Item"];

let mr_original_link_title = null;

function mr_is_link_title_hidden(doctype) {
    return !MR_HIDE_LINK_TITLE_FOR.length || MR_HIDE_LINK_TITLE_FOR.includes(doctype);
}

function mr_hide_link_title() {
    if (mr_original_link_title) return;

    mr_original_link_title = {
        get: frappe.utils.get_link_title,
        fetch: frappe.utils.fetch_link_title
    };

    // Mengembalikan name apa adanya; formatter Link menganggapnya "tanpa title".
    frappe.utils.get_link_title = function (doctype, name) {
        if (mr_is_link_title_hidden(doctype)) return name;
        return mr_original_link_title.get.apply(this, arguments);
    };

    frappe.utils.fetch_link_title = function (doctype, name) {
        if (mr_is_link_title_hidden(doctype)) return Promise.resolve(name);
        return mr_original_link_title.fetch.apply(this, arguments);
    };
}

function mr_restore_link_title() {
    if (!mr_original_link_title) return;

    frappe.utils.get_link_title = mr_original_link_title.get;
    frappe.utils.fetch_link_title = mr_original_link_title.fetch;
    mr_original_link_title = null;
}

function mr_sync_link_title() {
    const route = frappe.get_route() || [];
    if (route[1] === MR_DOCTYPE) {
        mr_hide_link_title();
    } else {
        mr_restore_link_title();
    }
}

if (!frappe.__mr_link_title_watcher) {
    frappe.__mr_link_title_watcher = true;
    frappe.router.on("change", mr_sync_link_title);
}

// frappe.ui.form.off("Material Request", "make_request_for_quotation")
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
        // dipanggil sebelum field dirender, supaya item_code tidak sempat tampil sebagai title
        mr_sync_link_title();

        // Stok hanya disegarkan untuk tampilan: set_value di sini membuat dokumen
        // yang baru dibuka langsung "Not Saved" begitu stok gudang sudah bergeser.
        if (frm.doc.docstatus == 0) {
            frm.doc.items.forEach(function (item) {
                get_stock_for_item(frm, item.doctype, item.name, true);
            });
        }
    },


    refresh(frm) {
        mr_sync_link_title();

        if (frm.is_new()) {
            frm.trigger('set_default_reqdate')
        }

        sth.form.override_class_function(frm.cscript, "onload", () => {
            frm.set_query("item_code", "items", sth.queries.item_by_subtype)
        })

        frm.set_query("divisi", sth.queries.divisi)
        frm.trigger('refresh_read_only_fields')
        if (frm.doc.docstatus == 1) {
            frm.remove_custom_button("Purchase Order", "Create")
            // frm.page.inner_toolbar.find(`div[data-label="${encodeURIComponent("Create")}"]`).remove()
        }

    },

    // make_request_for_quotation: function (frm) {
    //     frappe.model.open_mapped_doc({
    //         method: "sth.overrides.material_request.make_request_for_quotation",
    //         frm: frm,
    //         run_link_triggers: true,
    //     });
    // },


    unit(frm) {
        frm.trigger('set_unit_to_child')
    },

    purchase_type(frm) {
        if (!frm.doc.purchase_type) {
            frm.page.inner_toolbar.hide()
        } else {
            frm.page.inner_toolbar.show()
        }
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
                            query: "sth.controllers.queries.get_berita_acara",
                            filters: {
                                unit: frm.doc.unit
                            }
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
    },

    kendaraan(frm, dt, dn) {
        let row = locals[dt][dn]
        if (!frm.doc.ho && row.kendaraan) {
            frappe.xcall("frappe.client.get_value", {
                doctype: "Alat Berat Dan Kendaraan",
                filters: row.kendaraan,
                fieldname: ["kmhm_akhir"]
            }).then((res) => {
                frappe.model.set_value(dt, dn, "km_hm", res.kmhm_akhir)
            })
        } else {
            frappe.model.set_value(dt, dn, "km_hm", "")
        }
    }
})

function get_stock_for_item(frm, cdt, cdn, silent) {
    let row = locals[cdt][cdn];

    const set_stock = (value) => {
        if (!silent) {
            frappe.model.set_value(cdt, cdn, 'stock', value);
        } else if (row.stock !== value) {
            row.stock = value;
            frm.fields_dict.items.grid.refresh_row(cdn);
        }
    };

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
                        set_stock(stock_response.message || 0);
                    }
                });
            } else {
                set_stock(0);
                if (silent) return;
                frappe.msgprint(__('No central warehouse found for company {0} and unit {1}', [company, frm.doc.unit]));
            }
        }
    });
}
