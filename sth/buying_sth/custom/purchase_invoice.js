frappe.ui.form.on("Purchase Invoice", {
    setup(frm) {
        sth.form.setup_fieldname_select(frm, "items")

        sth.form.override_class_function(frm.cscript, "calculate_totals", () => {
            // tambahan disini
            frm.trigger("set_value_dpp_and_taxes")
        })
    },

    onload(frm) {
        frm._default_coa = {}

        frappe.xcall("sth.custom.purchase_invoice.get_default_coa", { type: "ppn", company: frm.doc.company }).then((res) => {
            frm._default_coa.ppn = res
        })
    },

    refresh(frm) {
        sth.form.setup_column_table_items(frm, frm.doc.invoice_type)
        frm.trigger("setup_queries")

        frm.add_custom_button(
            __("Training Event"),
            function () {
                showTrainingEventSelector(frm);
            }, __("Get Items From"));
    },

    setup_queries(frm) {

        frm.set_query("unit", function (doc) {
            return {
                filters: {
                    company: doc.company
                }
            }
        })

        frm.set_query("document_no", function (doc) {
            let filters = {
                company: doc.company,
                supplier: doc.supplier,
                docstatus: 1,
                // per_billed: ["<", 100]
            }

            return {
                filters: filters
            }
        })

        frm.set_query("item_code", "items", function (doc) {
            var filters = { 'supplier': doc.supplier, 'is_purchase_item': 1, 'has_variants': 0 }
            if (doc.purchase_type === "Non Voucher Match") {
                filters = { is_stock_item: 0, custom_is_expense: 1 }
            } else if (doc.is_subcontracted) {
                filters = { 'supplier': doc.supplier };
                if (doc.is_old_subcontracting_flow) {
                    filters["is_sub_contracted_item"] = 1;
                }
                else {
                    filters["is_stock_item"] = 0;
                }
            }

            return {
                query: "erpnext.controllers.queries.item_query",
                filters: filters
            }
        });
    },

    invoice_type(frm) {
        sth.form.setup_column_table_items(frm, frm.doc.invoice_type)
    },
    document_type(frm) {
        // remove nomor document
        frm.set_value("document_no", null)
    },

    document_no(frm) {
        function _map(data) {
            frm.set_value({
                supplier: data.nama_supplier,
                unit: data.unit,
                buying_price_list: data.jarak
            })

            frm.clear_table("items")

            for (const row of data.items) {
                let item = frm.add_child("items")
                item.item_code = row.item_code
                item.qty = row.qty
                item.rate = row.rate
                item.amount = row.total
                frm.script_manager.trigger("item_code", item.doctype, item.name)
            }

            if (data.beban_pph_22) {
                frappe.xcall("sth.custom.purchase_invoice.get_default_coa", { company: frm.doc.company, type: "PPH 22" }).then((res) => {
                    if (!res) {
                        return
                    }
                    frm.clear_table("taxes")
                    let item = frm.add_child("taxes")
                    item.charge_type = "On Net Total"
                    item.account_head = res
                    item.rate = data.percent
                    // frm.script_manager.trigger("rate", item.doctype, item.name)

                })
            }

            refresh_field("items")
            refresh_field("taxes")
        }

        if (frm.doc.nomor_pembelian) {
            frappe.dom.freeze("Mapping Data...")
            frappe.xcall("frappe.client.get", { doctype: "Pengakuan Pembelian TBS", name: frm.doc.nomor_pembelian })
                .then((res) => {
                    frappe.run_serially([
                        () => _map(res),
                        () => frappe.dom.unfreeze()
                    ])
                })
        }

    },

    set_value_dpp_and_taxes(frm) {
        frm.doc.dpp = frm.doc.net_total
        frm.doc.pph = frm.doc.taxes_and_charges_deducted
        for (const row of frm.doc.taxes) {
            if (row.account_head == frm._default_coa.ppn) {
                frm.doc.ppn = row.tax_amount
            }
        }
        frm.doc.biaya_lainnya = frm.doc.taxes_and_charges_added - frm.doc.ppn
        frm.refresh_fields()
    }
});

async function showTrainingEventSelector(frm) {
    if (!(frm.doc.supplier)) {
        frappe.msgprint(__("Lengkapi Supplier terlebih dahulu."));
        return;
    }

    const fields = [
        {
            fieldtype: 'Link',
            fieldname: 'name',
            label: 'Training Event',
            in_list_view: true
        },
        {
            fieldtype: 'Link',
            fieldname: 'supplier',
            label: 'Supplier',
            in_list_view: true
        },
        {
            fieldtype: 'Date',
            fieldname: 'custom_posting_date',
            label: 'Posting Date',
            in_list_view: true
        },
    ];

    let d = new frappe.ui.Dialog({
        title: 'Select Training Event',
        size: 'large',
        fields: [
            {
                label: 'Training Event',
                fieldname: 'table_training_event',
                fieldtype: 'Table',
                cannot_add_rows: true,
                in_place_edit: false,
                fields: fields
            }
        ],
        primary_action_label: 'Submit',
        async primary_action() {
            const selected_items = d.fields_dict.table_training_event.grid.get_selected_children();

            if (selected_items.length != 1) {
                frappe.throw("Select Only One Training Event")
            }

            const training_events = selected_items.map(r => r.name);
            const consting_items = await frappe.call({
                method: "sth.overrides.purchase_invoice.get_item_costing_in_training_events",
                args: {
                    training_events: training_events
                },
                freeze: true,
                freeze_message: "Mengambil costing training event...",
            });

            for (const costing of consting_items.message) {
                frm.add_child("items", {
                    item_code: costing.item,
                    item_name: costing.item_code,
                    qty: 1,
                    uom: costing.stock_uom,
                    rate: costing.total_amount,
                    base_rate: costing.total_amount,
                    amount: costing.total_amount,
                    base_amount: costing.total_amount,
                })
            }

            frm.fields_dict.items.grid.update_docfield_property(
                "custom_receipt_attachment",
                "hidden",
                false
            );

            frm.set_value("custom_reference_doctype", "Training Event");
            frm.set_value("custom_reference_name", selected_items[0].name);
            frm.refresh_field("items");
            frm.trigger("calculate_taxes_and_totals");
            d.hide();
        }
    });

    const training_events = await frappe.call({
        method: "sth.overrides.purchase_invoice.get_all_training_event_by_supplier",
        args: {
            supplier: frm.doc.supplier
        },
    });

    if (training_events.message) {
        d.fields_dict.table_training_event.df.data = training_events.message;
        d.fields_dict.table_training_event.refresh();
    }
    frm.clear_table("items");
    d.show();
}
