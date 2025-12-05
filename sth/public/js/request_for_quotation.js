frappe.ui.form.off("Request for Quotation", "make_supplier_quotation")
frappe.ui.form.on('Request for Quotation', {
    refresh(frm) {
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
