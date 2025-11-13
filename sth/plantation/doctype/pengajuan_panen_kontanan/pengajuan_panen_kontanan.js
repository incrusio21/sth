// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pengajuan Panen Kontanan", {
	refresh(frm) {
        frm.set_df_property("hasil_panen", "cannot_add_rows", true);
	}
});

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
        this.show_general_ledger()
    }

    set_query_field(){
        this.frm.set_query("bkm_panen", function(doc){
            return{
                filters: {
                    company: ["=", doc.company],
                    is_kontanan: 1,
                    is_rekap: 1,
                    against_salary_component: ["is", "not set"]
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
