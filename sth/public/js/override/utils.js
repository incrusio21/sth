erpnext.utils.map_current_doc = function (opts, opts_callback = null) {
    function _map() {
        if ($.isArray(cur_frm.doc.items) && cur_frm.doc.items.length > 0) {
            // remove first item row if empty
            if (!cur_frm.doc.items[0].item_code) {
                cur_frm.doc.items = cur_frm.doc.items.splice(1);
            }

            // find the doctype of the items table
            var items_doctype = frappe.meta.get_docfield(cur_frm.doctype, "items").options;

            // find the link fieldname from items table for the given
            // source_doctype
            var link_fieldname = null;
            frappe.get_meta(items_doctype).fields.forEach(function (d) {
                if (d.options === opts.source_doctype) link_fieldname = d.fieldname;
            });

            // search in existing items if the source_name is already set and full qty fetched
            var already_set = false;
            var item_qty_map = {};

            var removed_row = []

            $.each(cur_frm.doc.items, function (i, d) {
                opts.source_name.forEach(function (src) {
                    if (d[link_fieldname] == src) {
                        removed_row.push(d.name)
                        already_set = true;
                        if (item_qty_map[d.item_code]) item_qty_map[d.item_code] += flt(d.qty);
                        else item_qty_map[d.item_code] = flt(d.qty);
                    }
                });
            });

            if (already_set) {
                opts.source_name.forEach(function (src) {
                    frappe.model.with_doc(opts.source_doctype, src, function (r) {
                        var source_doc = frappe.model.get_doc(opts.source_doctype, src);
                        $.each(source_doc.items || [], function (i, row) {
                            if (row.qty > flt(item_qty_map[row.item_code])) {
                                already_set = false;
                                return false;
                            }
                        });
                    });

                    // if (already_set) {
                    //     frappe.msgprint(
                    //         __("You have already selected items from {0} {1}", [opts.source_doctype, src])
                    //     );
                    //     return;
                    // }
                });
            }
        }

        console.log(opts.source_name);

        return frappe.call({
            // Sometimes we hit the limit for URL length of a GET request
            // as we send the full target_doc. Hence this is a POST request.
            type: "POST",
            method: "frappe.model.mapper.map_docs",
            args: {
                method: opts.method,
                source_names: opts.source_name,
                target_doc: cur_frm.doc,
                args: opts.args,
            },
            freeze: true,
            freeze_message: __("Mapping {0} ...", [opts.source_doctype]),
            callback: function (r) {
                if (!r.exc) {
                    // start custom
                    r.message.items = r.message.items
                        .filter((row) => !removed_row.includes(row.name))
                        .map((item, index) => ({
                            ...item,
                            idx: index + 1
                        }))

                    // untuk menjalankan fungsi custom sebelum di sync
                    if (opts_callback) {
                        opts_callback(r.message)
                    }

                    // end custom
                    frappe.model.sync(r.message);
                    cur_frm.dirty();
                    cur_frm.refresh();
                }
            },
        });
    }

    // console.log("Masuk");


    let query_args = {};
    if (opts.get_query_filters) {
        query_args.filters = opts.get_query_filters;
    }

    if (opts.get_query_method) {
        query_args.query = opts.get_query_method;
    }

    if (query_args.filters || query_args.query) {
        opts.get_query = () => query_args;
    }

    if (opts.source_doctype) {
        let data_fields = [];
        if (["Purchase Receipt", "Delivery Note"].includes(opts.source_doctype)) {
            let target_meta = frappe.get_meta(cur_frm.doc.doctype);
            if (target_meta.fields.find((f) => f.fieldname === "taxes")) {
                data_fields.push({
                    fieldname: "merge_taxes",
                    fieldtype: "Check",
                    label: __("Merge taxes from multiple documents"),
                });
            }
        }
        const d = new frappe.ui.form.MultiSelectDialog({
            doctype: opts.source_doctype,
            target: opts.target,
            date_field: opts.date_field || undefined,
            setters: opts.setters,
            read_only_setters: opts.read_only_setters,
            data_fields: data_fields,
            get_query: opts.get_query,
            add_filters_group: 1,
            allow_child_item_selection: opts.allow_child_item_selection,
            child_fieldname: opts.child_fieldname,
            child_columns: opts.child_columns,
            size: opts.size,
            action: function (selections, args) {
                let values = selections;
                if (values.length === 0) {
                    frappe.msgprint(__("Please select {0}", [opts.source_doctype]));
                    return;
                }


                if (values.constructor === Array) {
                    opts.source_name = [...new Set(values)];
                } else {
                    opts.source_name = values;
                }

                if (
                    opts.allow_child_item_selection ||
                    ["Purchase Receipt", "Delivery Note", "Pick List"].includes(opts.source_doctype)
                ) {
                    // args contains filtered child docnames
                    opts.args = args;
                }
                d.dialog.hide();
                _map();
            },
        });

        return d;
    }

    if (opts.source_name) {
        opts.source_name = [opts.source_name];
        _map();
    }
};
