frappe.provide("sth.queries")

frappe.ui.form.on("Material Request", {
    refresh(frm) {
        frm.set_query("item_code", "items", sth.queries.item_by_subtype)
        frm.set_query("divisi", sth.queries.divisi)

        if (frm.doc.docstatus == 0) {
            frm.add_custom_button("Berita Acara", function () {
                frm.trigger('get_berita_acara')
            }, __("Get Items From"))
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
                    reqd: 1
                },
            ],
            primary_action_label: 'Get Items',
            primary_action(values) {
                frappe.dom.freeze("Getting Items...")

                frappe.xcall("frappe.client.get", {
                    doctype: "Berita Acara",
                    name: values.berita_acara
                }).then((res) => {
                    frm.clear_table('items')

                    res.table_klkc.forEach(row => {
                        let item = frm.add_child('items')
                        item.item_code = row.item_code
                        item.qty = row.jumlah
                        item.uom = row.uom
                    });

                    refresh_field("items");

                }).finally(() => {
                    frappe.dom.unfreeze()
                })

                d.hide();
            }
        })
        d.show()
    }
});