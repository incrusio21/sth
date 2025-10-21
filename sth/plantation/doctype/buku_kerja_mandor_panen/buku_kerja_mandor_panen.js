// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

sth.plantation.setup_bkm_controller()

// frappe.ui.form.on("Buku Kerja Mandor Panen", {
// 	refresh(frm) {

// 	},
// });

sth.plantation.BukuKerjaMandorPanen = class BukuKerjaMandorPanen extends sth.plantation.BKMController {
    setup(doc) {
        let me = this
        super.setup(doc)
        
        this.fieldname_total.push("jumlah_janjang", "qty_brondolan", "brondolan_amount", "denda")
        this.kegiatan_fetch_fieldname.push("upah_brondolan")
        
        this.hasil_kerja_update_field.push("buah_tidak_dipanen_rate", "buah_mentah_disimpan_rate",
            "buah_mentah_ditinggal_rate", "brondolan_tinggal_rate", "pelepah_tidak_disusun_rate", "pelepah_sengkleh_rate")
        
        this.setup_bkm(doc)

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
        if (item.parentfield != "hasil_kerja") return

        let doc = this.frm.doc

        item.rate = item.rate || this.frm.doc.rupiah_basis
        item.brondolan = doc.upah_brondolan

        item.hari_kerja = flt(item.qty / doc.volume_basis)
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
        item.sub_total = item.amount + item.brondolan_amount
    }

    after_calculate_grand_total(){
        this.frm.doc.grand_total -= this.frm.doc.hasil_kerja_denda
    }
}

cur_frm.script_manager.make(sth.plantation.BukuKerjaMandorPanen);