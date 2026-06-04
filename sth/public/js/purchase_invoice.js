// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Invoice", {
    onload(frm) {
        frm.trigger('set_due_date')

        frm.set_query("type", "ppn", function (doc, cdt, cdn) {
            return {
                filters: {
                    type: "PPN"
                }
            };
        });

        frm.set_query("type", "pph_lainnya", function (doc, cdt, cdn) {
            return {
                filters: {
                    type: "PPh"
                }
            };
        });
        // _apply_credit_to_filter(frm);
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

            check_and_show_button(frm);
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
    before_save: function(frm) {
        frappe.db.get_value('Account', 
            { account_number: '1156099', company: frm.doc.company }, 
            'name',
            function(r) {
                if (r && r.name) {
                    let account = r.name;
                    
                    frm.doc.items.forEach(function(row) {
                        
                        frappe.model.set_value(
                            row.doctype, 
                            row.name, 
                            'expense_account', 
                            account
                        );
                        
                    });
                    
                    frm.refresh_field('items');
                }
            }
        );
    },
    invoice_type: function(frm){
        // frm.set_value("credit_to", "");
        // _apply_credit_to_filter(frm);
    }
})

function _apply_credit_to_filter(frm) {
    if (frm.doc.invoice_type === "Leasing") {
        frm.set_query("credit_to", () => ({
            filters: {
                account_number: ["in", ["2212001", "2141101"]],
                company: frm.doc.company,
            },
        }));
    } else {
        // Kembalikan ke filter default ERPNext Purchase Invoice
        frm.set_query("credit_to", () => ({
            filters: {
                account_type: "Payable",
                is_group: 0,
                company: frm.doc.company,
            },
        }));
    }
 
    // Refresh field agar filter langsung aktif
    frm.refresh_field("credit_to");
}


frappe.ui.form.on("VAT Detail", {
    pph_lainnya_add(frm, dt, dn) {
        let row = locals[dt][dn]
        const tax = frm.add_child("taxes")
        tax.add_deduct_tax = "Deduct"
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
        frm.trigger('calculate_total_pph_lainnya')
        frm.trigger('calculate_total_ppn')
        frm.trigger('calculate_taxes_and_totals')
    },

    before_ppn_remove(frm, dt, dn) {
        let row = locals[dt][dn]
        frappe.model.clear_doc(row.ref_child_doc, row.ref_child_name)
        frm.trigger('calculate_total_pph_lainnya')
        frm.trigger('calculate_total_ppn')
        frm.trigger('calculate_taxes_and_totals')
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
        pph = 0 

        for (var baris in frm.doc.items){
            if(frm.doc.items[baris].pph == 1){
                pph = 1
            }
        }

        let amount = 0

        if(row.tax_type == "PPH"){
            if(pph == 1){
                pph_total = 0
                for (var baris in frm.doc.items){
                    if(frm.doc.items[baris].pph == 1){
                        pph_total += frm.doc.items[baris].amount
                    }
                }
                amount = pph_total * row.percentage / 100
            }
            else{
                amount = frm.doc.total * row.percentage / 100
            }
        }
        else{
            amount = frm.doc.total * row.percentage / 100
        }    
        
        frappe.model.set_value(row.ref_child_doc, row.ref_child_name, "tax_amount", amount)
        frappe.model.set_value(dt, dn, "amount", amount)
        frm.trigger('calculate_total_pph_lainnya')
        frm.trigger('calculate_total_ppn')
        frm.trigger('calculate_taxes_and_totals')
    }
})

async function check_and_show_button(frm) {
  // Ambil purchase order dari baris items (item pertama)
  const first_item = frm.doc.items?.[0];
  if (!first_item?.purchase_order) return;

  // Cek sub_purchase_type di item pertama PO
  const po = await frappe.db.get_doc("Purchase Order", first_item.purchase_order);

  if (po.sub_purchase_type !== "Service Request") return;

  // Tampilkan tombol
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

  // Buat pilihan item yang bisa dipecah (qty > 0)
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
          // Update info qty
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
        options: ["Bagian 1","Bagian 2"],
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

        // Update baris asli — gunakan set_value agar amount ikut terhitung
        frappe.model.set_value(original_row.doctype, original_row.name, {
            qty: qty1,
            amount: flt(qty1 * original_row.rate, precision("amount", original_row)),
            pph: pph_on_bagian1 ? 1 : 0
        });

        // Tambah baris baru
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

        // Hitung ulang semua total & taxes
        frm.trigger("calculate_taxes_and_totals");

        frm.dirty();
        frappe.show_alert({ message: "Item berhasil dipecah.", indicator: "green" });
        dialog.hide();
    },
  });

  dialog.show();
}