// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.provide("sth.legal");

frappe.ui.form.on("Ganti Rugi Lahan", {
	refresh(frm) {
        if(!frm.is_new()){
            frm.add_custom_button(__('Upload/View File'), function() {
                let submited_condition = frm.doc.docstatus > 0
                if(frm.doc.jenis_biaya == "GRLTT"){
                    submited_condition = frm.doc.docstatus > 1
                }
                new sth.utils.EfillingSelector(frm, frm.doc.jenis_biaya, submited_condition, (r) => {
                    // if (r) {
                    //     let update_values = {
                    //         serial_and_batch_bundle: r.name,
                    //         qty: Math.abs(r.total_qty),
                    //     };

                    //     if (!warehouse_field) {
                    //         warehouse_field = "warehouse";
                    //     }

                    //     if (r.warehouse) {
                    //         update_values[warehouse_field] = r.warehouse;
                    //     }

                    //     frappe.model.set_value(item_row.doctype, item_row.name, update_values);
                    // }
                });
            });
        }
	},
    company(frm) {
        frm.cscript.get_details_account({
            method: "sth.legal.doctype.ganti_rugi_lahan.ganti_rugi_lahan.fetch_company_account",
            args: {
                company: frm.doc.company,
                childrens: frm.doc.items.length > 0 ? frm.doc.items : null,
            }
        })
    },

    pembayaran_lahan(frm){
        frm.cscript.get_details_account({
            method: "sth.legal.doctype.ganti_rugi_lahan.ganti_rugi_lahan.get_details_sppt",
            args: {
                pembayaran_lahan: frm.doc.pembayaran_lahan,
                childrens: frm.doc.items.length > 0 ? frm.doc.items : null,
            }
        })
    },
});

frappe.ui.form.on("Ganti Rugi Lahan Item", {
    jenis_biaya(frm, cdt, cdn){
        let data = frappe.get_doc(cdt, cdn)

        frm.cscript.get_details_account({
            method: "sth.legal.doctype.ganti_rugi_lahan.ganti_rugi_lahan.get_details_jenis_biaya",
            args: {
                company: frm.doc.company,
                childrens: [data],
                sppt_update: 1 
            }
        })
    },
    sppt(frm, cdt, cdn){
        let data = frappe.get_doc(cdt, cdn)

        if(!data.sppt) return;

        frm.cscript.get_details_account({
            method: "sth.legal.doctype.ganti_rugi_lahan.ganti_rugi_lahan.get_details_sppt",
            args: {
                pembayaran_lahan: frm.doc.pembayaran_lahan,
                childrens: [data],
            }
        })
    }
});

sth.legal.GantiRugiLahan = class GantiRugiLahan extends sth.plantation.AccountsController {
    setup() {
        let me = this

        for (const fieldname of ["qty", "rate", "biaya_surat"]) {
            frappe.ui.form.on('Ganti Rugi Lahan Item', fieldname, function (doc, cdt, cdn) {
                me.calculate_total(cdt, cdn)
            });
        }
    }
    
    refresh() {
        this.show_general_ledger()
        this.set_query_field()
    }

    set_query_field() {
        this.frm.set_query("unit", function (doc) {
			return {
				filters: {
					company: ["=", doc.company]
				}
			};
		});

		this.frm.set_query("sppt", "items", function (doc, cdt, cdn) {
            let item = locals[cdt][cdn]

			return {
				filters: {
					perangkat_desa: ["=", item.perangkat_desa]
				}
			};
		});

        this.frm.set_query("pemilik_lahan", "items", function (doc, cdt, cdn) {
            let item = locals[cdt][cdn]

			return {
				filters: {
					pd: ["=", item.perangkat_desa]
				}
			};
		});
    }

    get_details_account(opts){
        let me = this

        frappe.call({
            method: opts.method,
            args: opts.args,
            callback: function(r) {
                if(!r.exc && r.message) {
                    for (const [key, value] of Object.entries(r.message)) {
                        if(key == "childrens"){
                            me._set_values_for_item_list(r.message.childrens, false)
                        }else{
                            me.frm.doc[key] = value
                        }
                    }

                    me.calculate_total()
                }
            }
        });
    }

    _set_values_for_item_list(children, recalculate=true) {
		for (const child of children) {
			let data = frappe.get_doc(child.doctype, child.name)

			for (const [key, value] of Object.entries(child)) {
				data[key] = value 
			}
		}

        if(recalculate) this.calculate_total();
	}

    calculate_total(){
        let doc = this.frm.doc

        let grand_total = 0

        for (const child of doc.items) {
            child.amount = flt(child.qty) * flt(child.rate) + flt(child.biaya_surat)
			grand_total += child.amount
		}

        doc.grand_total = flt(grand_total)

        this.frm.refresh_fields()
    }
}

cur_frm.script_manager.make(sth.legal.GantiRugiLahan);
