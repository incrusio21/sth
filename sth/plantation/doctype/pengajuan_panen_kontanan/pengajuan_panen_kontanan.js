// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pengajuan Panen Kontanan", {
	refresh(frm) {
        frm.set_df_property("hasil_panen", "cannot_add_rows", true);

        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__("GL Entry"), function() {
                frappe.route_options = {
                    voucher_no: frm.doc.name,
                    from_date: frm.doc.posting_date,
                    to_date: frm.doc.posting_date,
                    company: frm.doc.company,
                    group_by: "Group by Voucher (Consolidated)",
                };
                frappe.set_route("query-report", "General Ledger");
            }, __("View"));
        
        }
	},
    onload: function(frm) {
        if (frm.is_new()) {
            set_credit_to_from_settings(frm);
        }
    },

    company: function(frm) {
        set_credit_to_from_settings(frm);
    }
});

function set_credit_to_from_settings(frm) {
    if (!frm.doc.company) return;

    frappe.db.get_single_value('Plantation Settings', 'plantation_settings_pengajuan_panen_kontanan')
        .then(value => {
            if (!value) return;

        // value adalah nama doctype child table atau JSON — sesuaikan dengan struktur field
        // Asumsi: plantation_settings_pengajuan_panen_kontanan adalah child table
        frappe.db.get_doc('Plantation Settings')
            .then(settings => {
                const rows = settings.plantation_settings_pengajuan_panen_kontanan || [];
                const matched = rows.find(row => row.company === frm.doc.company);

                if (matched && matched.account) {
                    frm.set_value('credit_to', matched.account);
                } else {
                    frm.set_value('credit_to', '');
                }
            });
    });
}

sth.plantation.PengajuanPanenKontanan = class PengajuanPanenKontanan extends sth.plantation.TransactionController {
    setup(doc) {
        let me = this
        super.setup(doc)

        this.skip_calculate_table = ["hasil_panen"]

        for (const fieldname of ["upah_mandor", "upah_mandor1", "upah_kerani"]) {
            frappe.ui.form.on(doc.doctype, fieldname, function(doc, cdt, cdn) {
                me.calculate_total(cdt, cdn)
            });
        }
    }

    refresh() {
        super.refresh()
        // this.show_general_ledger()
    }

    set_query_field(){
        this.frm.set_query("bkm_panen", function(doc){
            return{
                filters: {
                    company: ["=", doc.company],
                    is_kontanan: 1,
                    is_rekap: 0,
                    against_salary_component: ["is", "not set"]
                }
            }
        })

        this.frm.set_query("credit_to", function(doc){
            return{
                filters: {
                    company: ["=", doc.company],
                    is_group: 0
                    
                }
            }
        })
        this.frm.set_query("salary_account", function(doc){
            return{
                filters: {
                    company: ["=", doc.company],
                    is_group: 0
                    
                }
            }
        })
    }
    
    before_calculate_grand_total() {
        let doc = this.frm.doc

        doc.upah_supervisi_amount = flt(doc.upah_mandor) + flt(doc.upah_mandor1) + flt(doc.upah_kerani)
    }
}

cur_frm.script_manager.make(sth.plantation.PengajuanPanenKontanan);
