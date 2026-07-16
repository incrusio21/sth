// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Invoice", {
    setup(frm) {
        sth.form.setup_fieldname_select(frm, "items")
    },

    onload(frm) {
        frm.trigger('set_due_date')

        if (frm.is_new() && frm.doc.pakai_ppn === undefined) {
            frm.set_value('pakai_ppn', 1)
        }

        frm.set_query("type", "ppn", function (doc, cdt, cdn) {
            return { filters: { type: "PPN" } };
        });

        frm.set_query("type", "pph_lainnya", function (doc, cdt, cdn) {
            return { filters: { type: "PPh" } };
        });

        frm.set_query("pilih_ppn", "non_voucher_match", function (doc, cdt, cdn) {
            return { filters: { type: "PPN" } };
        });

        frm.set_query("pilih_pph", "non_voucher_match", function (doc, cdt, cdn) {
            return { filters: { type: "PPh" } };
        });

        if (!frm.fields_dict.non_voucher_match) {
            // child table field 'non_voucher_match' assumed to exist
        }
    },

    refresh(frm) {
        if (frm.is_new() && frm.doc.invoice_type === "Pengakuan Pembelian TBS") {
            for (const row of (frm.doc.pph_lainnya || [])) {
                if (row.type && !row.account) {
                    frm.script_manager.trigger("type", row.doctype, row.name)
                }
            }
        }

        frm.trigger('get_tax_template')
        frm.page.sidebar.hide()

        if ((frm.doc.items || []).length) {
            calculate_sub_total(frm)

            // "Get Items From" (Purchase Receipt / Pengakuan Pembelian TBS) uses
            // erpnext.utils.map_current_doc, which replaces frm.doc in bulk via
            // frappe.model.sync + frm.refresh() instead of adding rows one by one,
            // so the "items_add" child-table event never fires for that flow.
            // Re-sync the PPN 12% row here so pakai_ppn isn't left empty.
            if (frm.doc.pakai_ppn && !(frm.doc.ppn || []).some(row => row.type === "PPN 12%")) {
                frm.trigger('pakai_ppn')
            }
        }

        sth.form.setup_column_table_items(frm, frm.doc.invoice_type)
        toggle_kegiatan_unit_columns(frm)
        frm.trigger("setup_queries")

        toggle_non_voucher_section(frm)
        if (frm.doc.voucher_type === 'Non Voucher Match') {
            set_coa_filter(frm)
        }

        frm.fields_dict["charges_purchase_invoice"].grid.update_docfield_property(
            "account", "get_query", function () {
                return {
                    filters: {
                        company: frm.doc.company,
                        is_group: 0
                    }
                };
            }
        );

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

            frm.add_custom_button(
                __("BAPP"),
                function () {
                    const _orig = frappe.call.bind(frappe);

                    frappe.call = function (opts, ...rest) {
                        if (
                            opts?.method === "frappe.model.mapper.map_docs" &&
                            opts?.args?.method?.includes("make_purchase_invoice")
                        ) {
                            frappe.call = _orig;
                            const bapp_name = (opts.args?.source_names || [])[0];
                            if (!bapp_name) return _orig(opts, ...rest);

                            frappe.db.get_value("BAPP", bapp_name, "proposal").then(({ message }) => {
                                const proposal = message?.proposal;
                                if (!proposal) {
                                    return _do_map(opts, bapp_name, null);
                                }

                                frappe.db.get_doc("Proposal", proposal).then(proposal_doc => {
                                    const rows = proposal_doc.kontraktor_proposal || [];
                                    const contractors = rows.map(r => r.kontraktor);
                                    if (contractors.length <= 1) {
                                        return _do_map(opts, bapp_name, null);
                                    }

                                    const dialog = new frappe.ui.Dialog({
                                        title: __("Pilih Supplier untuk Purchase Invoice"),
                                        fields: [
                                            {
                                                label: __("Supplier"),
                                                fieldname: "selected_supplier",
                                                fieldtype: "Link",
                                                options: "Supplier",
                                                reqd: 1,
                                                get_query: () => ({
                                                    filters: { name: ["in", contractors] }
                                                }),
                                                description: `${contractors.length} kontraktor tersedia. Qty akan dibagi rata (1/${contractors.length} per PI).`
                                            }
                                        ],
                                        primary_action_label: __("Lanjut"),
                                        primary_action(values) {
                                            dialog.hide();
                                            opts.args.args = opts.args.args || {};
                                            opts.args.args.selected_supplier = values.selected_supplier;
                                            _do_map(opts, bapp_name, values.selected_supplier);
                                        }
                                    });
                                    dialog.show();
                                });
                            });

                            return;
                        }

                        return _orig(opts, ...rest);
                    };

                    function _do_map(opts, bapp_name, selected_supplier) {
                        const _cb = opts.callback;
                        opts.callback = (r) => {
                            _cb && _cb(r);
                            show_pb_dialog(frm, bapp_name);
                        };
                        _orig(opts);
                    }

                    erpnext.utils.map_current_doc({
                        method: "sth.legal.doctype.bapp.bapp.make_purchase_invoice",
                        source_doctype: "BAPP",
                        target: frm,
                        setters: {
                            supplier: frm.doc.supplier || undefined,
                            posting_date: undefined,
                        },
                        get_query_filters: {
                            docstatus: 1,
                            status: ["not in", ["Closed", "Completed", "Return Issued"]],
                            company: frm.doc.company,
                        },
                    });
                },
                __("Get Items From")
            );

            check_and_show_button(frm);
        }

        if (frm.doc.docstatus === 0 || frm.is_new()) {
            frm.add_custom_button(
                __("Training Event"),
                function () {
                    showTrainingEventSelector(frm);
                }, __("Get Items From"));
        }
    },

    company(frm) {
        frm.trigger('get_tax_template')
    },

    voucher_type(frm) {
        toggle_non_voucher_section(frm);
        if (frm.doc.voucher_type === 'Non Voucher Match') {
            set_coa_filter(frm);
        }
    },

    invoice_type(frm) {
        sth.form.setup_column_table_items(frm, frm.doc.invoice_type)
        toggle_kegiatan_unit_columns(frm)
    },

    setup_queries(frm) {
        frm.set_query("unit", function (doc) {
            return { filters: { company: doc.company } }
        })

        frm.set_query("document_no", function (doc) {
            let filters = {}
            if (doc.invoice_type == "Pengakuan Pembelian TBS") {
                filters = {
                    company: doc.company,
                    nama_supplier: doc.supplier,
                    docstatus: 1,
                }
            } else {
                filters = {
                    company: doc.company,
                    supplier: doc.supplier,
                    docstatus: 1,
                }
            }
            return { filters }
        })

        frm.set_query("item_code", "items", function (doc) {
            var filters = { 'supplier': doc.supplier, 'is_purchase_item': 1, 'has_variants': 0 }
            if (doc.purchase_type === "Non Voucher Match") {
                filters = { is_stock_item: 0, custom_is_expense: 1 }
            } else if (doc.is_subcontracted) {
                filters = { 'supplier': doc.supplier };
                if (doc.is_old_subcontracting_flow) {
                    filters["is_sub_contracted_item"] = 1;
                } else {
                    filters["is_stock_item"] = 0;
                }
            }
            return {
                query: "erpnext.controllers.queries.item_query",
                filters: filters
            }
        });
    },

    document_type(frm) {
        frm.set_value("document_no", null)
    },

    document_no(frm) {
        if (!frm.doc.document_no) return

        if (frm.doc.invoice_type == "Pengakuan Pembelian TBS") {
            frappe.dom.freeze("Mapping Data...")
            frappe.xcall("frappe.client.get", { doctype: "Pengakuan Pembelian TBS", name: frm.doc.document_no })
                .then((res) => {
                    frappe.run_serially([
                        () => frm.events.tbs_map(frm, res),
                        () => frappe.dom.unfreeze()
                    ])
                })
                .finally(() => {
                    frappe.dom.unfreeze()
                })

        } else if (frm.doc.invoice_type == "Purchase Order") {
            frappe.dom.freeze("Mapping Data...")
            frappe.xcall("sth.buying_sth.custom.purchase_receipt.make_purchase_invoice", { source_name: frm.doc.document_no })
                .then((res) => {
                    res.name = frm.docname
                    res.invoice_type = frm.doc.invoice_type
                    res.document_type = frm.doc.document_type
                    res.document_no = frm.doc.document_no
                    frappe.model.sync(res)
                    frm.refresh()
                    frm.trigger('set_due_date')
                })
                .finally(() => {
                    frappe.dom.unfreeze()
                })
        }
    },

    tbs_map(frm, data) {
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

        refresh_field("items")
        refresh_field("taxes")
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
        sync_to_taxes(frm)
    },

    is_pph_22(frm) {
        if (!frm.doc.is_pph_22) {
            frm.set_value('pph_22', 0)
        }
    },

    pakai_ppn(frm) {
        toggle_ppn_12(frm)
    },

    items_add(frm) {
        frm.trigger('pakai_ppn')
    },

    pph_22(frm) {
        sync_to_taxes(frm)
    },

    pbbkb(frm) {
        sync_to_taxes(frm)
    },

    cost(frm) {
        sync_to_taxes(frm)
    },

    get_tax_template(frm) {
        frappe.provide('frappe.refererence.__ref_tax')
        if (Object.keys(frappe.refererence.__ref_tax).length === 0 && frm.doc.docstatus == 0) {
            if (!frm.doc.company) return

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

        if (!frm._diskon_account && frm.doc.company) {
            frappe.db.get_value("Account", { account_number: "5112999", company: frm.doc.company }, "name").then(r => {
                if (r && r.message && r.message.name) {
                    frm._diskon_account = r.message.name
                }
            })
        }
    },

    sub_total(frm) {
        const diskon = frm.doc.persentase_diskon || 0
        frm.set_value('jumlah_diskon', diskon * frm.doc.sub_total / 100)
    },

    persentase_diskon(frm) {
        const diskon = frm.doc.persentase_diskon || 0
        frm.set_value('jumlah_diskon', diskon * frm.doc.sub_total / 100)
    },

    jumlah_diskon(frm) {
        frm.trigger('recalculate_vat_details')
    },

    recalculate_vat_details(frm) {
        const base_pph = frm.doc.sub_total || 0
        const base_ppn = (frm.doc.sub_total || 0) - (frm.doc.jumlah_diskon || 0)

        // Hanya panggil set_value & sync_to_taxes kalau nilainya benar-benar
        // berubah. frappe.model.set_value dan sync_to_taxes (yang membongkar
        // ulang child table "taxes") SELALU menandai form dirty walau
        // nilainya persis sama dengan yang sudah tersimpan. Karena fungsi
        // ini juga dipanggil dari refresh() -> calculate_sub_total() setiap
        // dokumen dibuka, tanpa guard ini form langsung jadi "Not Saved"
        // padahal belum ada perubahan apa pun.
        let changed = false

        for (const row of (frm.doc.pph_lainnya || [])) {
            if (!row.percentage) continue
            const amount = base_pph * row.percentage / 100
            if (flt(row.amount) === flt(amount)) continue
            frappe.model.set_value(row.ref_child_doc, row.ref_child_name, "tax_amount", amount)
            frappe.model.set_value(row.doctype, row.name, "amount", amount)
            changed = true
        }

        for (const row of (frm.doc.ppn || [])) {
            if (!row.percentage) continue
            const amount = base_ppn * row.percentage / 100
            if (flt(row.amount) === flt(amount)) continue
            frappe.model.set_value(row.ref_child_doc, row.ref_child_name, "tax_amount", amount)
            frappe.model.set_value(row.doctype, row.name, "amount", amount)
            changed = true
        }

        frm.trigger('calculate_total_pph_lainnya')
        frm.trigger('calculate_total_ppn')
        if (changed) {
            sync_to_taxes(frm)
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

    set_value_dpp_and_taxes(frm) {
        frm.doc.dpp = frm.doc.net_total

        let total_ppn = 0
        let total_pph = 0
        let total_lainnya = 0
        for (const row of frm.doc.taxes) {
            if (row.tipe_pajak == "PPN") {
                total_ppn += row.tax_amount
            } else if (row.tipe_pajak == "PPH") {
                total_pph += row.tax_amount
            } else {
                total_lainnya += row.tax_amount
            }
        }

        frm.doc.ppn = total_ppn
        frm.doc.pph = total_pph
        frm.doc.biaya_lainnya = total_lainnya
        frm.refresh_fields()
    },

    async before_save(frm) {
        if ((frm.doc.items || []).length) {
            calculate_sub_total(frm)
        }

        // Must await this: before_save has to resolve only after the
        // account lookup + expense_account updates are applied. Previously
        // this used a callback, so save() completed before the callback
        // ran; frappe.model.set_value then fired *after* save and marked
        // the form dirty again, which made submit keep asking to save in
        // a loop.
        const r = await frappe.db.get_value('Account',
            { account_number: '1156099', company: frm.doc.company },
            'name'
        );
        const account = r && r.message && r.message.name;
        if (!account) return;

        let changed = false;
        frm.doc.items.forEach(function (row) {
            if (row.expense_account !== account) {
                frappe.model.set_value(row.doctype, row.name, 'expense_account', account);
                changed = true;
            }
        });
        if (changed) frm.refresh_field('items');
    },

    validate(frm) {
        if (frm.doc.voucher_type === 'Non Voucher Match') {
            process_non_voucher_entries(frm);
        }

        if (frm.doc.docstatus != 0) return

        const po_names = [...new Set(
            (frm.doc.items || [])
                .map((d) => d.purchase_order)
                .filter(Boolean)
        )]

        if (!po_names.length) return

        const promises = po_names.map((po_name) =>
            frappe.xcall('frappe.client.get', {
                doctype: 'Purchase Order',
                name: po_name,
                filters: { name: po_name }
            }).then((po) => {
                for (const tax of (po.taxes || [])) {
                    const exists = (frm.doc.taxes || []).find(
                        (t) => t.account_head === tax.account_head
                    )
                    if (exists) continue

                    const row = frm.add_child('taxes')
                    row.account_head   = tax.account_head
                    row.charge_type    = tax.charge_type
                    row.add_deduct_tax = tax.add_deduct_tax
                    row.tax_amount     = tax.tax_amount
                    row.description    = tax.description
                    row.tipe_pajak     = tax.tipe_pajak
                    row.category       = tax.category
                }
            })
        )

        return Promise.all(promises).then(() => {
            frm.refresh_field('taxes')
        })
    },
});


// ─── VAT Detail ───────────────────────────────────────────────────────────────

frappe.ui.form.on("VAT Detail", {
    pph_lainnya_add(frm, dt, dn) {
        sync_to_taxes(frm)
    },

    ppn_add(frm, dt, dn) {
        sync_to_taxes(frm)
    },

    pph_lainnya_remove(frm, dt, dn) {
        sync_to_taxes(frm);
        frm.trigger('calculate_total_pph_lainnya')
        frm.trigger('calculate_total_ppn')
        frm.trigger('calculate_taxes_and_totals')
    },

    ppn_remove(frm, dt, dn) {
        sync_to_taxes(frm);
        frm.trigger('calculate_total_pph_lainnya')
        frm.trigger('calculate_total_ppn')
        frm.trigger('calculate_taxes_and_totals')
    },

    amount(frm, dt, dn) {
        let row = locals[dt][dn]
        if (!row.ref_child_doc || !row.ref_child_name) return
        frappe.model.set_value(row.ref_child_doc, row.ref_child_name, "tax_amount", row.amount)
        frm.trigger('calculate_total_pph_lainnya')
        frm.trigger('calculate_total_ppn')
        sync_to_taxes(frm)
    },

    type(frm, dt, dn) {
        let row = locals[dt][dn]
        if (!frm.doc.company) {
            frappe.throw("Silahkan isi company lebih dahulu")
        }
        const tipe = row.parentfield == "ppn" ? "Masukan" : "PPh"
        frappe.xcall("sth.custom.supplier_quotation.get_account_tax_rate", { name: row.type, company: frm.doc.company, tipe: tipe }).then((res) => {
            frappe.model.set_value(dt, dn, "account", res)
            if(tipe == "PPh"){
                row.tax_type= "PPH"
            }
            else{
                row.tax_type="PPN"
            }
            frm.refresh_field(row.parentfield)
            sync_to_taxes(frm)
        })

},

    percentage(frm, dt, dn) {
        let row = locals[dt][dn]
        let base = 0

        // if(frm.doc.invoice_type == "SPK"){
        base = frm.doc.total

        let total_centang_pph = 0
        
        if(row.parentfield == "pph_lainnya"){
            for(var baris in frm.doc.items){
                var satu_baris = frm.doc.items[baris]
                if(satu_baris.pph == 1){
                    total_centang_pph += satu_baris.amount
                }
            }

            if(total_centang_pph > 0){
                base = total_centang_pph
            }
        }
        

        // }
        // else{
        //     base = row.parentfield == "pph_lainnya"
        //         ? (frm.doc.sub_total || 0)
        //         : (frm.doc.sub_total || 0) - (frm.doc.jumlah_diskon || 0)
        // }
       
        const amount = base * (row.percentage || 0) / 100

        frappe.model.set_value(row.ref_child_doc, row.ref_child_name, "tax_amount", amount)
        frappe.model.set_value(dt, dn, "amount", amount)
        frm.trigger('calculate_total_pph_lainnya')
        frm.trigger('calculate_total_ppn')
        sync_to_taxes(frm)
    }
});


// ─── Purchase Invoice Item ────────────────────────────────────────────────────

frappe.ui.form.on("Purchase Invoice Item", {
    qty(frm, cdt, cdn) {
        recalculate_item_amount(frm, cdt, cdn);
    },

    rate(frm, cdt, cdn) {
        recalculate_item_amount(frm, cdt, cdn);
    },

    amount(frm) {
        calculate_sub_total(frm);
    }
});

function recalculate_item_amount(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    const amount = flt(row.qty) * flt(row.rate);

    // frappe.model.set_value triggers the "amount" handler above, which
    // in turn calls calculate_sub_total -> recalculate_vat_details, so
    // sub_total and the ppn/pph_lainnya tables stay in sync with qty/rate.
    frappe.model.set_value(cdt, cdn, "amount", amount);
}


// ─── Purchase Invoice Pengeluaran Barang ──────────────────────────────────────

frappe.ui.form.on("Purchase Invoice Pengeluaran Barang", {
    amount(frm) {
        calculate_sub_total(frm);
        sync_to_taxes(frm);
    },
    purchase_invoice_pengeluaran_barang_remove(frm) {
        calculate_sub_total(frm);
        sync_to_taxes(frm);
    }
});



const CHARGES_MARKER = "__from_charges__";
const PB_MARKER = "__from_pb__";

function sync_to_taxes(frm){
    frm.doc.taxes = []
    sync_charges_to_taxes(frm, true)
    sync_pb_to_taxes(frm, true)
    sync_diskon_to_taxes(frm, true)
    sync_pph_lainnya_to_taxes(frm, true)
    sync_ppn_to_taxes(frm, true)
    sync_all_to_taxes(frm)

    frm.refresh_field("taxes");
    frm.trigger("calculate_taxes_and_totals");
}
function sync_diskon_to_taxes(frm, skip_recalc = false) {

    const DISKON_MARKER = "__diskon__"

    // bersihkan row diskon lama dulu
    frm.doc.taxes = (frm.doc.taxes || []).filter(
        row => !(row.description || "").startsWith(DISKON_MARKER)
    )

    const jumlah_diskon = frm.doc.jumlah_diskon || 0
    const diskon_account = frm._diskon_account
    if (jumlah_diskon && diskon_account) {
        let diskon_row = frm.add_child("taxes")
        diskon_row.charge_type = "Actual"
        diskon_row.category = "Total"
        diskon_row.account_head = diskon_account
        diskon_row.tax_amount = -jumlah_diskon
        diskon_row.add_deduct_tax = "Add"
        diskon_row.description = DISKON_MARKER
    }
}

function sync_pb_to_taxes(frm, skip_recalc = false) {
    (frm.doc.purchase_invoice_pengeluaran_barang || []).forEach(pb => {
        if (!pb.account || !pb.amount) return;

        let new_row = frm.add_child("taxes");
        new_row.charge_type = "Actual";
        new_row.category = "Total";
        new_row.account_head = pb.account;
        new_row.tax_amount = -pb.amount;
        new_row.tax_amount_after_discount_amount = -pb.amount;
        new_row.add_deduct_tax = "Add";
        new_row.description = `${PB_MARKER}${pb.pengeluaran_barang_item || ""}`;
    });

    if (!skip_recalc) {
        frm.refresh_field("taxes");
        frm.trigger("calculate_taxes_and_totals");
    }
}


// ─── Charges Purchase Invoice ─────────────────────────────────────────────────

frappe.ui.form.on("Charges Purchase Invoice", {
    account(frm, cdt, cdn) {
        sync_to_taxes(frm);
    },
    total(frm, cdt, cdn) {
        sync_to_taxes(frm);
    },
    keterangan(frm, cdt, cdn) {
        sync_to_taxes(frm);
    },
    charges_purchase_invoice_remove(frm) {
        sync_to_taxes(frm);
    }
});

function sync_charges_to_taxes(frm, skip_recalc = false) {
    // frm.doc.taxes = (frm.doc.taxes || []).filter(
    //     row => !(row.description || "").startsWith(CHARGES_MARKER)
    // );

    let total_charges = 0;

    (frm.doc.charges_purchase_invoice || []).forEach(charge => {
        if (!charge.account || !charge.total) return;

        total_charges += charge.total;

        let new_row = frm.add_child("taxes");
        new_row.charge_type = "Actual";
        new_row.category = "Total";
        new_row.account_head = charge.account;
        new_row.tax_amount = charge.total;
        new_row.tax_amount_after_discount_amount = charge.total;
        new_row.description = `${CHARGES_MARKER}${charge.keterangan || ""}`;
    });

    frm.set_value("total_charges", total_charges);

    if (!skip_recalc) {
        frm.refresh_field("taxes");
        calculate_sub_total(frm);
        frm.trigger("calculate_taxes_and_totals");
    }
}


// ─── Non Voucher Match ────────────────────────────────────────────────────────

frappe.ui.form.on('Non Voucher Match', {
    form_render(frm, cdt, cdn) {
        frm.fields_dict['non_voucher_match'].grid.get_field('coa').get_query = function (doc) {
            return {
                filters: {
                    'company': doc.company,
                    'is_group': 0
                }
            };
        };
    },

    dpp(frm, cdt, cdn) {
        calculate_non_voucher_row(frm, cdt, cdn);
    },

    ppn(frm, cdt, cdn) {
        calculate_non_voucher_row(frm, cdt, cdn);
    },

    pph(frm, cdt, cdn) {
        calculate_non_voucher_row(frm, cdt, cdn);
    },

    persen_ppn(frm, cdt, cdn) {
        calculate_non_voucher_row(frm, cdt, cdn);
    },

    persen_pph(frm, cdt, cdn) {
        calculate_non_voucher_row(frm, cdt, cdn);
    }
});

function toggle_non_voucher_section(frm) {
    if (frm.doc.voucher_type === 'Non Voucher Match') {
        frm.set_df_property('non_voucher_match', 'hidden', 0);
        frm.set_df_property('items', 'hidden', 1);
    } else {
        frm.set_df_property('non_voucher_match', 'hidden', 1);
        frm.set_df_property('items', 'hidden', 0);
    }
    frm.refresh_fields();
}

function toggle_kegiatan_unit_columns(frm) {
    const hidden = frm.doc.invoice_type !== "SPK" ? 1 : 0;

    ["kegiatan", "kegiatan_name", "unit"].forEach(fieldname => {
        frm.fields_dict.items.grid.update_docfield_property(fieldname, "hidden", hidden);
    });

    frm.fields_dict.items.grid.refresh();
}

function toggle_ppn_12(frm) {
    const PPN_TYPE = "PPN 12%";
    const PPN_PERCENTAGE = 12;

    if (frm.doc.pakai_ppn) {
        const exists = (frm.doc.ppn || []).some(row => row.type === PPN_TYPE);
        if (!exists) {
            let row = frm.add_child("ppn");
            row.type = PPN_TYPE;
            row.percentage = PPN_PERCENTAGE;
            frm.refresh_field("ppn");
            frm.script_manager.trigger("type", row.doctype, row.name);
            frm.script_manager.trigger("percentage", row.doctype, row.name);
        }
    } else {
        frm.clear_table("ppn");
        frm.refresh_field("ppn");
        frm.trigger('calculate_total_ppn');
        sync_to_taxes(frm);
    }
}

function set_coa_filter(frm) {
    frm.set_query('coa', 'non_voucher_match', function (doc) {
        return {
            filters: {
                'company': doc.company,
                'is_group': 0
            }
        };
    });
}

function process_non_voucher_entries(frm) {
    if (!frm.doc.non_voucher_match || frm.doc.non_voucher_match.length === 0) return;

    if (!frm.doc.company) {
        frappe.throw(__('Please select a Company first'));
        return;
    }

    frappe.call({
        method: 'frappe.client.get',
        args: { doctype: 'Company', name: frm.doc.company },
        async: false,
        callback(r) {
            if (!r.message) return;
            let company = r.message;

            if (!company.account_default_item) {
                frappe.throw(__('Account Default Item is not set in Company'));
                return;
            }
            if (!company.ppn_account) {
                frappe.throw(__('PPN Account is not set in Company'));
                return;
            }
            if (!company.pph_account) {
                frappe.throw(__('PPh Account is not set in Company'));
                return;
            }

            // Bangun dulu data items/taxes yang seharusnya ada, tanpa
            // menyentuh frm.doc, supaya bisa dibandingkan dengan data yang
            // sudah ada. clear_table + add_child SELALU membuat form dirty
            // walau isinya sama persis, dan validate() ini juga jalan saat
            // submit, sehingga tiap submit selalu mengubah dokumen lagi dan
            // memaksa save ulang tanpa henti. Rebuild hanya dilakukan kalau
            // datanya benar-benar berbeda.
            let new_items = [];
            let total_ppn = 0;
            let total_pph = 0;

            frm.doc.non_voucher_match.forEach((nv_row) => {
                new_items.push({
                    item_code: company.account_default_item,
                    item_name: company.account_default_item,
                    description: nv_row.description || 'Non Voucher Entry',
                    qty: 1,
                    rate: nv_row.dpp || 0,
                    amount: nv_row.dpp || 0,
                    uom: "Nos",
                    expense_account: nv_row.coa,
                });

                total_ppn += (nv_row.ppn || 0);
                total_pph += (nv_row.pph || 0);
            });

            const kept_taxes = (frm.doc.taxes || []).filter(
                row => (row.description || "").startsWith(CHARGES_MARKER)
            );

            let new_tax_rows = [];
            if (total_ppn != 0) {
                new_tax_rows.push({
                    charge_type: 'Actual',
                    account_head: company.ppn_account,
                    description: 'PPN',
                    tax_amount: total_ppn,
                    tipe_pajak: "PPN",
                });
            }
            if (total_pph != 0) {
                new_tax_rows.push({
                    charge_type: 'Actual',
                    account_head: company.pph_account,
                    description: 'PPh',
                    tax_amount: -total_pph,
                    tipe_pajak: "PPH",
                });
            }

            const current_taxes = (frm.doc.taxes || []).filter(
                row => !(row.description || "").startsWith(CHARGES_MARKER)
            );

            const item_fields = ["item_code", "description", "qty", "rate", "amount", "uom", "expense_account"];
            const tax_fields = ["charge_type", "account_head", "description", "tax_amount", "tipe_pajak"];

            const needs_rebuild =
                !rows_match(frm.doc.items, new_items, item_fields) ||
                !rows_match(current_taxes, new_tax_rows, tax_fields);

            if (!needs_rebuild) return;

            frm.clear_table('items');
            frm.doc.taxes = kept_taxes;

            new_items.forEach((data) => Object.assign(frm.add_child('items'), data));
            new_tax_rows.forEach((data) => Object.assign(frm.add_child('taxes'), data));

            frm.refresh_field('items');
            frm.refresh_field('taxes');
        }
    });
}

function rows_match(existing, incoming, fields) {
    const rows = existing || [];
    if (rows.length !== incoming.length) return false;

    return rows.every((row, i) =>
        fields.every((f) => {
            const a = row[f];
            const b = incoming[i][f];
            return typeof a === "number" || typeof b === "number"
                ? flt(a || 0) === flt(b || 0)
                : (a || "") === (b || "");
        })
    );
}

function calculate_non_voucher_row(frm, cdt, cdn) {
    calculate_ppn_from_percentage(frm, cdt, cdn);
    calculate_pph_from_percentage(frm, cdt, cdn);
    let row = locals[cdt][cdn];

    if (row.dpp) {
        row.dpp_nilai_lainnya = (row.dpp * 11) / 12;
    }

    row.total = (row.dpp || 0) + (row.ppn || 0) - (row.pph || 0);
    frm.refresh_field('non_voucher_match');
}

function calculate_ppn_from_percentage(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (row.persen_ppn && row.dpp) {
        row.ppn = (row.dpp * row.persen_ppn) / 100;
    }
}

function calculate_pph_from_percentage(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (row.persen_pph && row.dpp) {
        row.pph = (row.dpp * row.persen_pph) / 100;
    }
}


// ─── Helper Functions ─────────────────────────────────────────────────────────

async function _get_tax_rate_account(tax_rate_name, tipe) {
    try {
        const doc = await frappe.xcall("frappe.client.get", {
            doctype: "Tax Rate",
            name: tax_rate_name,
        });
        const match = (doc.tax_rate_account || []).find(r.tipe == tipe
        );
        return match?.account || null;
    } catch(e) {
        console.warn(`_get_tax_rate_account: gagal fetch Tax Rate "${tax_rate_name}"`, e);
        return null;
    }
}

function sync_pph_lainnya_to_taxes(frm, skip_recalc = false) {
    const PPH_LAINNYA_MARKER = "__from_pph_lainnya__";

    for (const row of (frm.doc.pph_lainnya || [])) {
        if (!row.amount || !row.type) continue;

        let tax = frm.add_child("taxes");
        tax.account_head = row.account
        tax.charge_type = "Actual";
        tax.add_deduct_tax = "Add";
        tax.category = "Total";
        tax.tax_amount = row.amount * -1 || 0;
        tax.description = `${PPH_LAINNYA_MARKER}${row.type || ""}`;
    }

    frm.refresh_field("taxes");
    frm.trigger("calculate_taxes_and_totals");
    
}

function sync_ppn_to_taxes(frm, skip_recalc = false) {
    const PPN_MARKER = "__from_ppn__";

    for (const row of (frm.doc.ppn || [])) {
        if (!row.amount || !row.type) continue;

        let tax = frm.add_child("taxes");
        tax.account_head = row.account
        tax.charge_type = "Actual";
        tax.add_deduct_tax = "Add";
        tax.category = "Total";
        tax.tax_amount = row.amount || 0;
        tax.description = `${PPN_MARKER}${row.type || ""}`;
    }

    frm.refresh_field("taxes");
    frm.trigger("calculate_taxes_and_totals");
}

function sync_all_to_taxes(frm) {
    const ref_tax = frappe.refererence.__ref_tax || {}
    const field_map = [
        { key: "Ongkos Angkut", value: frm.doc.total_biaya_ongkos_angkut, add_deduct: "Add" },
        { key: "PPH 22",        value: frm.doc.pph_22,                     add_deduct: "Add" },
        { key: "PBBKB",         value: frm.doc.pbbkb,                      add_deduct: "Add" },
        { key: "Cost",          value: frm.doc.cost,                        add_deduct: "Add" },
    ]

    for (const { key, value, add_deduct } of field_map) {
        const ref = ref_tax[key]
        if (!ref) continue

        let tax = (frm.doc.taxes || []).find(r => r.account_head == ref.account)
        if (!tax) {
            tax = frm.add_child("taxes")
            tax.account_head = ref.account
            tax.charge_type = "Actual"
            tax.add_deduct_tax = add_deduct
            tax.category = "Total"
        }
        frappe.model.set_value(tax.doctype, tax.name, "tax_amount", value || 0)
    }
}

function calculate_sub_total(frm) {
    let sub_total = 0;
    if (frm.doc.voucher_type === "Non Voucher Match") {
        sub_total = (frm.doc.non_voucher_match || []).reduce((sum, r) => sum + (r.total || 0), 0);
    } else {
        const total_items = (frm.doc.items || []).reduce((sum, r) => sum + (r.amount || 0), 0);
        const total_charges = (frm.doc.charges_purchase_invoice || []).reduce((sum, r) => sum + (r.total || 0), 0);
        const total_pb = (frm.doc.purchase_invoice_pengeluaran_barang || []).reduce((sum, r) => sum + (r.amount || 0), 0);
        sub_total = total_items + total_charges - total_pb;
    }

    // frm.set_value('jumlah_diskon', ...) di handler sub_total() hanya memicu
    // trigger jumlah_diskon->recalculate_vat_details kalau nilainya berubah.
    // Kalau diskon 0%, nilainya tetap sama sehingga tabel ppn/pph_lainnya
    // tidak ikut ter-update saat qty/amount items berubah. Panggil langsung
    // di sini supaya selalu tersinkron. Tapi ini juga dipanggil dari
    // refresh() setiap dokumen dibuka, jadi hanya trigger kalau sub_total
    // memang berubah dari yang tersimpan — kalau tidak, form akan langsung
    // jadi "Not Saved" begitu dokumen dibuka walau belum ada yang diedit.
    const sub_total_changed = flt(frm.doc.sub_total || 0) !== flt(sub_total);
    frm.set_value("sub_total", sub_total);

    if (sub_total_changed) {
        frm.trigger('recalculate_vat_details');
    }
}

function _apply_credit_to_filter(frm) {
    if (frm.doc.invoice_type === "Leasing") {
        frm.set_query("credit_to", () => ({
            filters: {
                account_number: ["in", ["2212001", "2141101"]],
                company: frm.doc.company,
            },
        }));
    } else {
        frm.set_query("credit_to", () => ({
            filters: {
                account_type: "Payable",
                is_group: 0,
                company: frm.doc.company,
            },
        }));
    }
    frm.refresh_field("credit_to");
}

async function check_and_show_button(frm) {
    const first_item = frm.doc.items?.[0];
    if (!first_item?.purchase_order) return;

    const po = await frappe.db.get_doc("Purchase Order", first_item.purchase_order);
    if (po.sub_purchase_type !== "Service Request") return;

    frm.add_custom_button("Pecah Item", () => {
        show_pecah_dialog(frm);
    });
}

function show_pecah_dialog(frm) {
    const items = frm.doc.items;
    if (!items || items.length === 0) {
        frappe.msgprint("Tidak ada item untuk dipecah.");
        return;
    }

    const item_options = items
        .filter((r) => r.qty > 0)
        .map((r) => ({
            label: `${r.item_name || r.item_code} — Qty: ${r.qty} — Harga: ${format_currency(r.rate)}`,
            value: r.name,
        }));

    const dialog = new frappe.ui.Dialog({
        title: "Pecah Item",
        fields: [
            {
                label: "Pilih Item",
                fieldname: "item_row",
                fieldtype: "Select",
                options: item_options.map((o) => o.label).join("\n"),
                reqd: 1,
                change() {
                    const selected_label = dialog.get_value("item_row");
                    const opt = item_options.find((o) => o.label === selected_label);
                    if (!opt) return;
                    const row = items.find((r) => r.name === opt.value);
                    if (row) {
                        dialog.set_value("qty_original", row.qty);
                        dialog.set_value("qty_bagian1", "");
                        dialog.set_value("qty_bagian2", "");
                    }
                },
            },
            {
                label: "Qty Original",
                fieldname: "qty_original",
                fieldtype: "Float",
                read_only: 1,
            },
            {
                label: "Qty Bagian 1",
                fieldname: "qty_bagian1",
                fieldtype: "Float",
                reqd: 1,
                description: "Masukkan qty untuk bagian pertama",
                change() {
                    const qty_original = dialog.get_value("qty_original");
                    const qty1 = dialog.get_value("qty_bagian1");
                    if (qty_original && qty1 !== undefined) {
                        const qty2 = flt(qty_original - qty1, 9);
                        dialog.set_value("qty_bagian2", qty2);
                    }
                },
            },
            {
                label: "Qty Bagian 2 (sisa)",
                fieldname: "qty_bagian2",
                fieldtype: "Float",
                read_only: 1,
            },
            {
                label: "Tandai PPH di bagian",
                fieldname: "pph_on",
                fieldtype: "Select",
                options: ["Bagian 1", "Bagian 2"],
                reqd: 1,
                description: "Pilih baris mana yang akan dicentang sebagai PPH",
            },
        ],
        primary_action_label: "Pecah",
        primary_action(values) {
            const opt = item_options.find((o) => o.label === values.item_row);
            if (!opt) return;

            const original_row = items.find((r) => r.name === opt.value);
            if (!original_row) return;

            const qty1 = flt(values.qty_bagian1);
            const qty2 = flt(values.qty_bagian2);

            if (qty1 <= 0 || qty2 <= 0) {
                frappe.msgprint("Qty masing-masing bagian harus lebih dari 0.");
                return;
            }

            if (Math.abs(qty1 + qty2 - original_row.qty) > 0.0001) {
                frappe.msgprint("Total qty bagian harus sama dengan qty original.");
                return;
            }

            const pph_on_bagian1 = values.pph_on === "Bagian 1";

            frappe.model.set_value(original_row.doctype, original_row.name, {
                qty: qty1,
                amount: flt(qty1 * original_row.rate, precision("amount", original_row)),
                pph: pph_on_bagian1 ? 1 : 0
            });

            const new_row = frm.add_child("items");

            const fields_to_copy = [
                "item_code", "item_name", "description", "uom", "conversion_factor",
                "rate", "price_list_rate", "discount_percentage", "expense_account",
                "cost_center", "purchase_order", "po_detail", "purchase_receipt",
                "pr_detail", "custom_merk"
            ];

            fields_to_copy.forEach((f) => {
                if (original_row[f] !== undefined) new_row[f] = original_row[f];
            });

            new_row.qty = qty2;
            new_row.pph = pph_on_bagian1 ? 0 : 1;
            new_row.amount = flt(qty2 * original_row.rate, precision("amount", original_row));

            frm.refresh_field("items");
            frm.trigger("calculate_taxes_and_totals");
            frm.dirty();
            frappe.show_alert({ message: "Item berhasil dipecah.", indicator: "green" });
            dialog.hide();
        },
    });

    dialog.show();
}

function show_pb_dialog(frm, bapp) {
    frappe.call({
        method: "sth.legal.doctype.bapp.bapp.get_unclaimed_pengeluaran_barang_items",
        args: { bapp },
        callback(r) {
            const items = r.message || [];
            if (!items.length) return;

            const fmt = (val) => frappe.format(val, { fieldtype: "Currency" });

            const rows = items
                .map(
                    (item, idx) => `
                    <tr>
                        <td class="text-center">
                            <input type="checkbox" class="pb-check" data-idx="${idx}" checked />
                        </td>
                        <td>${item.kode_barang}</td>
                        <td>${item.item_name}</td>
                        <td class="text-right">${item.jumlah} ${item.satuan || ""}</td>
                        <td class="text-right">${fmt(item.rate)}</td>
                        <td class="text-right">${fmt(item.amount)}</td>
                    </tr>`
                )
                .join("");

            const d = new frappe.ui.Dialog({
                title: __("Pengeluaran Barang Belum Ditagihkan"),
                fields: [
                    {
                        fieldtype: "HTML",
                        options: `
                            <div style="overflow-x:auto">
                                <table class="table table-bordered table-condensed" style="font-size:12px">
                                    <thead class="grid-heading-row">
                                        <tr>
                                            <th style="width:40px">
                                                <input type="checkbox" id="pb-check-all" checked />
                                            </th>
                                            <th>Kode Barang</th>
                                            <th>Nama Barang</th>
                                            <th class="text-right">Qty</th>
                                            <th class="text-right">Rate</th>
                                            <th class="text-right">Amount</th>
                                        </tr>
                                    </thead>
                                    <tbody>${rows}</tbody>
                                </table>
                            </div>`,
                    },
                ],
                primary_action_label: __("Tambahkan"),
                primary_action() {
                    const selected = [];
                    d.$wrapper.find(".pb-check:checked").each(function () {
                        selected.push(items[parseInt($(this).data("idx"))]);
                    });

                    if (!selected.length) {
                        frappe.msgprint(__("Pilih minimal satu item."));
                        return;
                    }

                    selected.forEach((item) => {
                        const row = frm.add_child("purchase_invoice_pengeluaran_barang");
                        row.kode_barang = item.kode_barang;
                        row.nama_barang = item.item_name;
                        row.qty = item.jumlah;
                        row.rate = item.rate;
                        row.amount = item.amount;
                        row.account = item.account;
                        row.pengeluaran_barang_item = item.name;
                    });

                    frm.refresh_field("purchase_invoice_pengeluaran_barang");
                    calculate_sub_total(frm);
                    sync_to_taxes(frm);
                    d.hide();
                },
            });

            d.show();

            d.$wrapper.find("#pb-check-all").on("change", function () {
                d.$wrapper.find(".pb-check").prop("checked", this.checked);
            });
        },
    });
}

async function showTrainingEventSelector(frm) {
    // if (!(frm.doc.supplier)) {
    //     frappe.msgprint(__("Lengkapi Supplier terlebih dahulu."));
    //     return;
    // }

    const fields = [
        { fieldtype: 'Link', fieldname: 'name', label: 'Training Event', in_list_view: true },
        { fieldtype: 'Link', fieldname: 'supplier', label: 'Supplier', in_list_view: true },
        { fieldtype: 'Date', fieldname: 'custom_posting_date', label: 'Posting Date', in_list_view: true },
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
                args: { training_events: training_events },
                freeze: true,
                freeze_message: "Mengambil costing training event...",
            });

            // for (const costing of consting_items.message) {
            //     frm.add_child("items", {
            //         item_code: costing.item,
            //         item_name: costing.item_code,
            //         qty: 1,
            //         uom: costing.stock_uom,
            //         rate: costing.total_amount,
            //         base_rate: costing.total_amount,
            //         amount: costing.total_amount,
            //         base_amount: costing.total_amount,
            //         keterangan: costing.expense_type,
            //     })
            // }

            // frm.fields_dict.items.grid.update_docfield_property("custom_receipt_attachment", "hidden", false);
            // console.log(selected_items[0].name)
            // frm.set_value("document_type", "Training Event");
            // frm.set_value("document_no", selected_items[0].name);
            // frm.set_value("invoice_type", "Jasa Pelatihan");
            // frm.set_value("supplier", selected_items[0].supplier);
            // frm.refresh_field("items");
            // frm.doc.document_no = selected_items[0].name
            // frm.refresh_field("document_no")
            // frm.trigger("calculate_taxes_and_totals");

            d.hide();

            await showPPHSelector(
                frm,
                selected_items[0],
                consting_items.message
            );
        }
    });

    const training_events = await frappe.call({
        method: "sth.overrides.purchase_invoice.get_all_training_event",
        args: {  },
    });

    if (training_events.message) {
        d.fields_dict.table_training_event.df.data = training_events.message;
        d.fields_dict.table_training_event.refresh();
    }
    frm.clear_table("items");
    d.show();
}

async function showPPHSelector(frm, selected_training_event, costing_items) {

    console.log("test "+selected_training_event.name);

    const pph_dialog = new frappe.ui.Dialog({
        title: "Pilih Item PPh",
        size: "large",
        fields: [
            {
                fieldtype: "Table",
                fieldname: "table_pph",
                label: "Item PPh",
                cannot_add_rows: true,
                in_place_edit: true,
                fields: [
                    {
                        fieldtype: "Data",
                        fieldname: "expense_type",
                        label: "Expense Type",
                        read_only: 1,
                        in_list_view: 1
                    },
                    {
                        fieldtype: "Currency",
                        fieldname: "total_amount",
                        label: "Amount",
                        read_only: 1,
                        in_list_view: 1
                    },
                    {
                        fieldtype: "Check",
                        fieldname: "pph",
                        label: "PPh",
                        in_list_view: 1
                    }
                ]
            }
        ],
        primary_action_label: "Submit",
        primary_action: async function () {

            frm.clear_table("items");

            const rows = pph_dialog.fields_dict.table_pph.df.data;

            rows.forEach(r => {

                frm.add_child("items", {
                    item_code: r.item,
                    item_name: r.item_code,
                    qty: 1,
                    uom: r.stock_uom,
                    rate: r.total_amount,
                    base_rate: r.total_amount,
                    amount: r.total_amount,
                    base_amount: r.total_amount,
                    keterangan: r.expense_type,
                    pph: r.pph ? 1 : 0
                });

            });

            frm.fields_dict.items.grid.update_docfield_property(
                "custom_receipt_attachment",
                "hidden",
                false
            );

            await frm.set_value("supplier", selected_training_event.supplier);

            await frm.set_value("unit", selected_training_event.unit);

            await frm.set_value("document_type", "Training Event");

            await frm.set_value("invoice_type", "Jasa Pelatihan");

            await frm.set_value("document_no", selected_training_event.name);

            frm.refresh_field("items");
            frm.refresh_field("document_no");

            frm.trigger("calculate_taxes_and_totals");

            pph_dialog.hide();
        }
    });

    pph_dialog.fields_dict.table_pph.df.data = costing_items;
    pph_dialog.fields_dict.table_pph.refresh();

    pph_dialog.show();
}