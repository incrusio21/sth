// Copyright (c) 2025, DAS and Contributors
// MIT License. See license.txt

sth.plantation.setup_bkm_controller = function() {
    sth.plantation.BKMController = class BKMController extends sth.plantation.TransactionController {
        setup(doc) {
            super.setup(doc)
            
            this.fieldname_total.push("qty", "hari_kerja")
            
            this.kegiatan_fetch_fieldname = ["account as kegiatan_account", "volume_basis", "rupiah_basis"]

            this.get_data_rkh_field = ["kegiatan", "divisi", "posting_date", "blok"]
            this.hasil_kerja_update_field = ["volume_basis", "rupiah_basis"]
        }

        refresh() {
            super.refresh()
            sth.form.show_reset_payment_log(this.frm)
        }

        setup_bkm(doc){
            let me = this

            for (const fieldname of this.get_data_rkh_field) {
                frappe.ui.form.on(doc.doctype, fieldname, function () {
                    // me.get_rkh_data()
                });
            }
            
            // calculate grand total lagi jika field berubah
            for (const fieldname of this.hasil_kerja_update_field) {
                frappe.ui.form.on(doc.doctype, fieldname, function (frm) {
                    if(fieldname == "rupiah_basis"){
                        for (const hk of doc.hasil_kerja) hk.rate = frm.doc.rupiah_basis
                    }
                    
                    me.calculate_total(null, null, "hasil_kerja")
                });
            }
        }
        
        set_query_field() {
            super.set_query_field()

            this.frm.set_query("blok", function (doc) {

                return {
                    filters: {
                        divisi: ["=", doc.divisi],
                    }
                }
            })
        }

        get_rkh_data() {
            let me = this
            let doc = this.frm.doc
            
            // Validasi dasar
            const invalid =
                !doc.kegiatan ||
                !doc.divisi ||
                !doc.posting_date ||
                (doc.is_bibitan ? !doc.batch : !doc.blok);

            if (invalid) return;

            const blok = doc.is_bibitan ? doc.batch : doc.blok;
            
            frappe.call({
                method: "sth.controllers.queries.get_rencana_kerja_harian",
                args: {
                    kode_kegiatan: doc.kegiatan,
                    divisi: doc.divisi,
                    posting_date: doc.posting_date,
                    blok,
                    is_bibitan: doc.is_bibitan
                },
                freeze: true,
                callback: function (data) {
                    me.frm.set_value(data.message)
                }
            })
        }
    }
}
