frappe.ui.form.on("Supplier Quotation", {
    setup(frm) {
        // sth.form.override_class_function(frm.cscript, "calculate_totals", () => {
        //     frm.trigger("set_value_dpp_and_taxes")
        // })

        sth.form.override_class_function(frm.cscript, "refresh", () => {
            frm.trigger("create_custom_buttons")
        })

        frm.set_query("type", "pph_lainnya", function (doc) {
            return {
                filters: {
                    name: ["like", "%PPh%"]
                }
            }
        })

    },
    onload(frm) {

    },
    refresh(frm) {
        frm.page.btn_secondary.hide()
        if (frm.doc.workflow_state == "Approved") {
            frm.add_custom_button(__("Re open"), function () {
                let rfq = frm.doc.items[0].request_for_quotation
                frappe.xcall("sth.custom.supplier_quotation.reopen_rfq", { name: rfq, freeze: true })
                    .then((res) => {
                        // console.log("Oke")
                        frm.reload_doc()
                    })
            })
        } else {
            frm.remove_custom_button(__("Re open"))
        }
    },

    company(frm) {
        console.log("Oke");
    },

    ppn_biaya_ongkos(frm) {
        frm.trigger('calculate_biaya_angkot')
    },

    is_ppn_ongkos(frm) {
        frm.trigger('calculate_biaya_angkot')
    },

    biaya_ongkos(frm) {
        frm.trigger('calculate_biaya_angkot')
    },

    calculate_biaya_angkot(frm) {
        const ppn_biaya = frm.doc.ppn_biaya_ongkos
        const is_ppn = frm.doc.is_ppn_ongkos
        const biaya_ongkos = is_ppn ? (ppn_biaya / 100 * frm.doc.biaya_ongkos) + frm.doc.biaya_ongkos : frm.doc.biaya_ongkos
        frm.set_value("total_biaya_ongkos_angkut", biaya_ongkos)
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
    },

    create_custom_buttons(frm) {
        frm.remove_custom_button("Material Request", "Get Items From")
        frm.remove_custom_button("Request for Quotation", "Get Items From")
        if (frm.doc.docstatus === 0) {
            btn_get_material_request(frm)
            btn_get_rfq(frm)
        }
    }
})


frappe.ui.form.on("PPH Detail", {
    pph_lainnya_add(frm, dt, dn) {
        let row = locals[dt][dn]
        const tax = frm.add_child("taxes")
        frappe.model.set_value(dt, dn, {
            "ref_child_doc": tax.doctype,
            "ref_child_name": tax.name
        })

    },

    before_pph_lainnya_remove(frm, dt, dn) {
        let row = locals[dt][dn]
        frappe.model.clear_doc(row.ref_child_doc, row.ref_child_name)
    },

    percentage(frm, dt, dn) {
        let row = locals[dt][dn]
        frappe.model.set_value(dt, dn, "amount", frm.doc.total * row.percentage)
    }
})


function btn_get_material_request(frm) {
    frm.add_custom_button(
        __("Material Request"),
        function () {
            const d = erpnext.utils.map_current_doc({
                // method: "erpnext.stock.doctype.material_request.material_request.make_supplier_quotation",
                method: "sth.overrides.material_request.make_supplier_quotation",
                source_doctype: "Material Request",
                target: frm,
                allow_child_item_selection: 1,
                child_fieldname: "items",
                child_columns: ["item_code", "item_name", "qty", "uom", "unit"],
                size: "extra-large",
                setters: {
                    unit: undefined,
                },
                get_query_filters: {
                    material_request_type: "Purchase",
                    docstatus: 1,
                    status: ["!=", "Stopped"],
                    per_ordered: ["<", 100],
                    company: frm.doc.company,
                },
            }, () => {
                frm.trigger('calculate_totals')
            });

            setTimeout(() => {
                // console.log(d.dialog);
                d.dialog.set_value("allow_child_item_selection", 1)
            }, 1000);

        },
        __("Get Items From")
    );
}

function btn_get_rfq(frm) {
    frm.add_custom_button(
        __("Request for Quotation"),
        function () {
            if (!frm.doc.supplier) {
                frappe.throw({ message: __("Please select a Supplier"), title: __("Mandatory") });
            }
            const d = erpnext.utils.map_current_doc({
                // method: "erpnext.buying.doctype.request_for_quotation.request_for_quotation.make_supplier_quotation_from_rfq",
                method: "sth.overrides.request_for_quotation.make_supplier_quotation_from_rfq",
                source_doctype: "Request for Quotation",
                target: frm,
                allow_child_item_selection: 1,
                child_fieldname: "items",
                child_columns: ["item_code", "item_name", "qty", "uom", "unit"],
                size: "extra-large",
                setters: {
                    transaction_date: null,
                    unit: undefined,
                },
                get_query_filters: {
                    supplier: frm.doc.supplier,
                    company: frm.doc.company,
                },
                get_query_method:
                    "erpnext.buying.doctype.request_for_quotation.request_for_quotation.get_rfq_containing_supplier",
            }, () => {
                frm.trigger('calculate_totals')
            });

            setTimeout(() => {
                // console.log(d.dialog);
                d.dialog.set_value("allow_child_item_selection", 1)
            }, 1000);
        },
        __("Get Items From")
    );
}