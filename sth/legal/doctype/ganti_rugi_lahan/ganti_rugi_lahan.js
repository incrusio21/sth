// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.provide("sth.legal");

frappe.ui.form.on("Ganti Rugi Lahan", {
	// refresh(frm) {

	// },
    
    pembayaran_lahan(frm){
        frm.trigger("fetch_gis")
    },

    sppt(frm){
        frm.trigger("fetch_gis")
    },

    fetch_gis(frm){
        frm.call({
            doc: frm.doc,
            method: "fetch_sppt_data",
            callback: (r) => {
                frm.cscript.calculate_total()
            },
        })
    },
});

sth.legal.GantiRugiLahan = class GantiRugiLahan extends sth.plantation.AccountsController {
    setup() {
        let me = this

        for (const fieldname of ["qty", "rate", "biaya_surat"]) {
            frappe.ui.form.on('Ganti Rugi Lahan', fieldname, function (doc, cdt, cdn) {
                me.calculate_total(cdt, cdn)
            });
        }
    }
    
    refresh() {
        this.show_general_ledger()
    }

    company() {
        this.get_accounts()
    }

    jenis_biaya() {
        this.get_accounts()
    }

    get_accounts(){
        let me = this

        frappe.call({
            method: "sth.legal.doctype.ganti_rugi_lahan.ganti_rugi_lahan.fetch_company_account",
            args: {
                company: me.frm.doc.company,
                jenis_biaya: me.frm.doc.jenis_biaya,
            },
            callback: function(r) {
                if(!r.exc && r.message) {
                    me.frm.set_value(r.message);
                }
            }
        });
    }

    calculate_total(){
        let doc = this.frm.doc

        doc.grand_total = flt(doc.qty) * flt(doc.rate) + flt(doc.biaya_surat)

        this.frm.refresh_fields()
    }
}

cur_frm.script_manager.make(sth.legal.GantiRugiLahan);
