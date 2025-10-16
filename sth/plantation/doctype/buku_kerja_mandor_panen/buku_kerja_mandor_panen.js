// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Buku Kerja Mandor Panen", {
// 	refresh(frm) {

// 	},
// });

sth.plantation.BukuKerjaMandorPerawatan = class BukuKerjaMandorPerawatan extends sth.plantation.TransactionController {
    setup(doc) {
        super.setup(doc)

        this.fieldname_total.push("hari_kerja", "qty", "qty_brondolan", "brondolan_amount", "denda")
        this.kegiatan_fetch_fieldname = ["account as kegiatan_account", "volume_basis", "rupiah_basis", "persentase_premi", "rupiah_premi", "upah_brondolan"]

        let me = this
        
        for (const fieldname of ["kegiatan", "divisi", "blok", "posting_date"]) {
            frappe.ui.form.on(doc.doctype, fieldname, function () {
                // me.get_rkh_data()
            });
        }

        for (const fieldname of ["hari_kerja", "buah_tidak_dipanen_rate", "buah_mentah_disimpan_rate",
            "buah_mentah_ditinggal_rate", "brondolan_tinggal_rate", "pelepah_tidak_disusun_rate", "pelepah_sengkleh_rate"]) {
            frappe.ui.form.on(doc.doctype, fieldname, function (doc, cdt, cdn) {
                me.calculate_total(cdt, cdn, "hasil_kerja")
            });
        }

        for (const fieldname of ["jumlah_janjang", "qty_brondolan", "buah_tidak_dipanen", "buah_mentah_disimpan", "buah_mentah_ditinggal", "brondolan_tinggal",
            "pelepah_tidak_disusun", "tangkai_panjang", "buah_tidak_disusun", "pelepah_sengkleh"
        ]) {
            frappe.ui.form.on('Detail BKM Hasil Kerja Panen', fieldname, function (doc, cdt, cdn) {
                me.calculate_total(cdt, cdn)
            });
        }
    }

    set_query_field() {
        super.set_query_field()

        this.frm.set_query("blok", function (doc) {
            if (!doc.divisi) {
                frappe.throw("Please Select Divisi First")
            }

            return {
                filters: {
                    divisi: doc.divisi,
                }
            }
        })

        this.frm.set_query("kegiatan", function (doc) {
            return {
                filters: {
                    tipe_kegiatan: "Panen",
                    company: ["=", doc.company],
                }
            }
        })

    }

    update_rate_or_qty_value(item) {
        let doc = this.frm.doc
        
        item.rate = item.rate || doc.rupiah_basis
        item.brondolan = doc.upah_brondolan

        item.hari_kerja = flt(item.jumlah_janjang / doc.volume_basis)
    }

    update_value_after_amount(item) {
        let doc = this.frm.doc

        // Daftar faktor yang mempengaruhi denda
        let factors = [
            "buah_tidak_dipanen", "buah_mentah_disimpan", "buah_mentah_ditinggal",
            "brondolan_tinggal", "pelepah_tidak_disusun", "tangkai_panjang",
            "buah_tidak_disusun", "pelepah_sengkleh"
        ];

        // Hitung total denda
        item.denda = factors.reduce((total, field) => {
            return total + flt(item[field]) * flt(doc[`${field}_rate`]);
        }, 0);

        //  Hitung total brondolan
		item.brondolan_amount = flt(item.brondolan * flt(item.qty_brondolan))
    }

    after_calculate_grand_total(){
        this.frm.doc.grand_total -= this.frm.doc.hasil_kerja_denda
    }

    get_rkh_data() {
        let me = this
        let doc = this.frm.doc
        if (!(doc.kegiatan && doc.divisi && doc.blok && doc.posting_date)) return

        frappe.call({
            method: "sth.controllers.queries.get_rencana_kerja_harian",
            args: {
                kode_kegiatan: doc.kegiatan,
                divisi: doc.divisi,
                blok: doc.blok,
                posting_date: doc.posting_date
            },
            freeze: true,
            callback: function (data) {
                me.frm.set_value(data.message)
            }
        })
    }
}

cur_frm.script_manager.make(sth.plantation.BukuKerjaMandorPerawatan);