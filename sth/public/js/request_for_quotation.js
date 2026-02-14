frappe.ui.form.off("Request for Quotation", "make_supplier_quotation")
frappe.ui.form.on('Request for Quotation', {
    setup(frm) {
        const old_refresh = frm.cscript.refresh
        frm.cscript.refresh = function (...args) {
            old_refresh && old_refresh.apply(this, args);

            frm.page.inner_toolbar.find(`div[data-label="${encodeURIComponent('Get Items From')}"]`).remove()
            frm.page.inner_toolbar.find(`div[data-label="${encodeURIComponent('Tools')}"]`).remove()

            this.frm.add_custom_button(
                __("Material Request"), function () {
                    const d = erpnext.utils.map_current_doc({
                        method: "sth.overrides.material_request.make_request_for_quotation",
                        source_doctype: "Material Request",
                        target: frm,
                        allow_child_item_selection: 1,
                        child_fieldname: "items",
                        child_columns: ["item_code", "item_name", "qty", "uom", "unit"],
                        size: "extra-large",
                        setters: {
                            schedule_date: undefined,
                            status: undefined,
                            unit: undefined,
                        },
                        get_query_filters: {
                            material_request_type: "Purchase",
                            docstatus: 1,
                            status: ["!=", "Stopped"],
                            per_ordered: ["<", 100],
                            company: frm.doc.company,
                        },
                    }, (res) => {
                        console.log(res);
                    });

                    setTimeout(() => {
                        // console.log(d.dialog);
                        d.dialog.set_value("allow_child_item_selection", 1)
                    }, 500);

                },
                __("Get Items From")
            );
        }

        frm.set_query("lokasi_pengiriman", function (doc) {
            return {
                filters: {
                    company: doc.company
                }
            }
        })
    },

    onload_post_render(frm) {
        // frm.trigger('remove_listener_edit_item')
        // frm.set_df_property("items", "cannot_add_rows", true)
        // frm.trigger('add_duplicate_button_items')
    },

    add_duplicate_button_items(frm) {
        frm.get_field('items').$wrapper.on("click.duplicate", ".grid-row-check", function (e) {
            console.log(this)
        })
    },

    remove_listener_edit_item(frm) {
        frm.get_field('items').$wrapper.find('.btn-open-row').off('click')
    },

    make_supplier_quotation: function (frm) {
        var doc = frm.doc;
        var dialog = new frappe.ui.Dialog({
            title: __("Create Supplier Quotation"),
            fields: [
                {
                    fieldtype: "Link",
                    label: __("Supplier"),
                    fieldname: "supplier",
                    options: "Supplier",
                    reqd: 1,
                },
            ],
            primary_action_label: __("Create"),
            primary_action: (args) => {
                if (!args) return;
                dialog.hide();
                return frappe.call({
                    type: "GET",
                    method: "erpnext.buying.doctype.request_for_quotation.request_for_quotation.make_supplier_quotation_from_rfq",
                    args: {
                        source_name: doc.name,
                        for_supplier: args.supplier,
                    },
                    freeze: true,
                    callback: function (r) {
                        if (!r.exc) {
                            var doc = frappe.model.sync(r.message);
                            frappe.set_route("Form", r.message.doctype, r.message.name);
                        }
                    },
                });
            },
        });

        dialog.show();
    },
})

frappe.form.link_formatters['Item'] = function (value, doc) {
    return doc.item_name || doc.item_code
}
