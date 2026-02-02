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
        frm.set_value("apply_discount_on", "Net Total")
    },
    refresh(frm) {
        frm.trigger('get_tax_template')
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
        frm.trigger('get_tax_template')
    },

    ppn_biaya_ongkos(frm) {
        frm.trigger('calculate_total_biaya_angkut')
    },

    is_ppn_ongkos(frm) {
        if (!frm.doc.is_ppn_ongkos) {
            frm.doc.ppn_biaya_ongkos = 0
        }

        frm.trigger('calculate_total_biaya_angkut')
    },

    biaya_ongkos(frm) {
        frm.trigger('calculate_total_biaya_angkut')
    },

    total_biaya_ongkos_angkut(frm) {
        if (frappe.refererence.__ref_tax["Ongkos Angkut"]) {
            let coa = frappe.refererence.__ref_tax["Ongkos Angkut"].account
            let tax = frm.doc.taxes.find((r) => r.account_head == coa)
            if (tax) {
                frappe.model.set_value(tax.doctype, tax.name, "tax_amount", frm.doc.total_biaya_ongkos_angkut)
                frm.trigger('calculate_taxes_and_totals')
            }
        }
    },

    is_pph_22(frm) {
        if (!frm.doc.is_pph_22) {
            frm.set_value('pph_22', 0)
        }
    },

    pph_22(frm) {
        if (frappe.refererence.__ref_tax["PPH 22"]) {
            let coa = frappe.refererence.__ref_tax["PPH 22"].account
            let tax = frm.doc.taxes.find((r) => r.account_head == coa)
            if (tax) {
                frappe.model.set_value(tax.doctype, tax.name, "tax_amount", frm.doc.pph_22)
                frm.trigger('calculate_taxes_and_totals')
            }
        }
    },

    pbbkb(frm) {
        if (frappe.refererence.__ref_tax["PBBKB"]) {
            let coa = frappe.refererence.__ref_tax["PBBKB"].account
            let tax = frm.doc.taxes.find((r) => r.account_head == coa)
            if (tax) {
                frappe.model.set_value(tax.doctype, tax.name, "tax_amount", frm.doc.pbbkb)
                frm.trigger('calculate_taxes_and_totals')
            }
        }
    },

    get_tax_template(frm) {
        frappe.provide('frappe.refererence.__ref_tax')
        if (Object.keys(frappe.refererence.__ref_tax).length === 0) {
            if (!frm.doc.company) {
                return
            }

            frappe.xcall("sth.custom.supplier_quotation.get_taxes_template", { "company": frm.doc.company }).then((res) => {
                for (const row of res) {
                    let taxes = frm.add_child('taxes')
                    taxes.account_head = row.account
                    taxes.add_deduct_tax = "Add"
                    taxes.charge_type = "Actual"
                    frm.script_manager.trigger(taxes.doctype, taxes.name, "account_head")
                    frappe.refererence.__ref_tax[row.type] = row
                }
            })
        }
    },

    calculate_total_biaya_angkut(frm) {
        const ppn_biaya = frm.doc.ppn_biaya_ongkos
        const is_ppn = frm.doc.is_ppn_ongkos
        const biaya_ongkos = is_ppn ? (ppn_biaya / 100 * frm.doc.biaya_ongkos) + frm.doc.biaya_ongkos : frm.doc.biaya_ongkos
        frm.set_value("total_biaya_ongkos_angkut", biaya_ongkos)
    },

    calculate_total_pph_lainnya(frm) {
        let total = 0
        for (const row of frm.doc.pph_lainnya) {
            total += row.amount
        }

        frm.set_value("total_pph_lainnya", total)
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


frappe.ui.form.on("VAT Detail", {
    pph_lainnya_add(frm, dt, dn) {
        let row = locals[dt][dn]
        const tax = frm.add_child("taxes")
        tax.add_deduct_tax = "Add"
        tax.charge_type = "Actual"

        frappe.model.set_value(dt, dn, {
            "ref_child_doc": tax.doctype,
            "ref_child_name": tax.name
        })

    },

    type(frm, dt, dn) {
        let row = locals[dt][dn]

        if (!frm.doc.company) {
            frappe.throw("Silahkan isi company lebih dahulu")
        }
        frappe.xcall("sth.custom.supplier_quotation.get_account_tax_rate", { name: row.type, company: frm.doc.company }).then((res) => {
            frappe.model.set_value(row.ref_child_doc, row.ref_child_name, "account_head", res)
            frm.script_manager.trigger(row.ref_child_doc, row.ref_child_name, "account_head")
        })
    },

    before_pph_lainnya_remove(frm, dt, dn) {
        let row = locals[dt][dn]
        frappe.model.clear_doc(row.ref_child_doc, row.ref_child_name)
    },

    percentage(frm, dt, dn) {
        let row = locals[dt][dn]
        const amount = frm.doc.total * row.percentage / 100

        frappe.model.set_value(row.ref_child_doc, row.ref_child_name, "tax_amount", amount)
        frappe.model.set_value(dt, dn, "amount", amount)
        frm.trigger('calculate_total_pph_lainnya')
        frm.trigger('calculate_taxes_and_totals')
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
                frm.doc.__after_get_data = 1
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