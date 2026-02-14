// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Invoice", {
    onload(frm) {
        frm.trigger('set_due_date')
    },
    refresh(frm) {
        frm.trigger('get_tax_template')
        frm.page.sidebar.hide()
        if (frm.doc.docstatus == 0) {
            frm.add_custom_button(
                __("Pengakuan Pembelian TBS"),
                function () {
                    erpnext.utils.map_current_doc({
                        method: "sth.sales_sth.doctype.pengakuan_pembelian_tbs.pengakuan_pembelian_tbs.make_purchase_invoice",
                        source_doctype: "Pengakuan Pembelian TBS",
                        target: frm,
                        setters: {
                            nama_supplier: frm.doc.supplier || undefined,
                            unit: frm.doc.unit || undefined,
                            tanggal: undefined,
                        },
                        get_query_filters: {
                            docstatus: 1,
                            nama_supplier: frm.doc.supplier,
                            unit: frm.doc.unit,
                        },
                    });
                },
                __("Get Items From")
            );
        }
    },

    company(frm) {
        frm.trigger('get_tax_template')
    },

    set_due_date(frm) {
        if (frm.is_new()) {
            frm.set_value('due_date', frappe.datetime.add_days(frm.doc.posting_date, frm.doc.accept_day))
        }
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
        if (Object.keys(frappe.refererence.__ref_tax).length === 0 && frm.doc.docstatus == 0) {
            if (!frm.doc.company) {
                return
            }

            frappe.xcall("sth.custom.supplier_quotation.get_taxes_template", { "company": frm.doc.company }).then((res) => {
                for (const row of res) {
                    if (frm.is_new()) {
                        let taxes = frm.add_child('taxes')
                        taxes.account_head = row.account
                        taxes.add_deduct_tax = "Add"
                        taxes.charge_type = "Actual"
                        frm.script_manager.trigger(taxes.doctype, taxes.name, "account_head")
                    }
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

    calculate_total_ppn(frm) {
        let total = 0
        for (const row of frm.doc.ppn) {
            total += row.amount
        }

        frm.set_value("total_ppn", total)
    },
})


frappe.ui.form.on("VAT Detail", {
    pph_lainnya_add(frm, dt, dn) {
        let row = locals[dt][dn]
        const tax = frm.add_child("taxes")
        tax.add_deduct_tax = "Add"
        tax.charge_type = "Actual"

        frappe.model.set_value(dt, dn, {
            "ref_child_doc": tax.doctype,
            "ref_child_name": tax.name,
            "tax_type": "PPH"
        })

    },

    ppn_add(frm, dt, dn) {
        let row = locals[dt][dn]
        const tax = frm.add_child("taxes")
        tax.add_deduct_tax = "Add"
        tax.charge_type = "Actual"

        frappe.model.set_value(dt, dn, {
            "ref_child_doc": tax.doctype,
            "ref_child_name": tax.name,
            "tax_type": "PPN"
        })

    },

    before_pph_lainnya_remove(frm, dt, dn) {
        let row = locals[dt][dn]
        frappe.model.clear_doc(row.ref_child_doc, row.ref_child_name)
    },

    before_ppn_remove(frm, dt, dn) {
        let row = locals[dt][dn]
        frappe.model.clear_doc(row.ref_child_doc, row.ref_child_name)
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

    percentage(frm, dt, dn) {
        let row = locals[dt][dn]
        const amount = frm.doc.total * row.percentage / 100

        frappe.model.set_value(row.ref_child_doc, row.ref_child_name, "tax_amount", amount)
        frappe.model.set_value(dt, dn, "amount", amount)
        frm.trigger('calculate_total_pph_lainnya')
        frm.trigger('calculate_total_ppn')
        frm.trigger('calculate_taxes_and_totals')
    }
})