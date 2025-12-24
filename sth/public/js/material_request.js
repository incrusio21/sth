frappe.provide("sth.queries")

frappe.ui.form.on("Material Request", {
    refresh(frm) {
        if (frm.is_new()) {
            frm.trigger('set_default_reqdate')
        }

        frm.set_query("item_code", "items", sth.queries.item_by_subtype)
        frm.set_query("divisi", sth.queries.divisi)

        if (frm.doc.docstatus == 0) {
            frm.add_custom_button("Berita Acara", function () {
                frm.trigger('get_berita_acara')
            }, __("Get Items From"))
        }
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

    get_berita_acara(frm) {
        const d = new frappe.ui.Dialog({
            title: 'Get Items From Berita Acara',
            fields: [
                {
                    label: 'Berita Acara',
                    fieldname: 'berita_acara',
                    fieldtype: 'Link',
                    options: "Berita Acara",
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
                    let fields_update = ["unit", "sub_purchase_type", "purchase_type"]
                    for (const field of fields_update) {
                        frm.doc[field] = res[field]
                    }

                    frm.clear_table("items")
                    for (const data of res.items) {
                        frm.add_child("items", data)
                    }

                    frm.refresh()
                })

                d.hide();
            }
        })
        d.show()
    }
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
    }
})