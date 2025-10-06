// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Buku Kerja Mandor Panen", {
// 	refresh(frm) {

// 	},
// });

sth.plantation.BukuKerjaMandorPerawatan = class BukuKerjaMandorPerawatan extends sth.plantation.TransactionController {
    setup(doc) {
        super.setup(doc)

        this.fieldname_total.push("hari_kerja", "qty", "qty_brondolan")
        this.kegiatan_fetch_fieldname = ["account as kegiatan_account", "volume_basis", "rupiah_basis", "persentase_premi", "rupiah_premi", "upah_brondolan"]

        let me = this
        for (const fieldname of ["hari_kerja", "buah_tidak_dipanen_rate", "buah_mentah_disimpan_rate",
            "buah_mentah_ditinggal_rate", "brondolan_tinggal_rate", "pelepah_tidak_disusun_rate", "pelepah_sengkleh_rate"]) {
            frappe.ui.form.on(doc.doctype, fieldname, function (doc, cdt, cdn) {
                me.calculate_total(cdt, cdn, "hasil_kerja")
            });
        }

        for (const fieldname of ["kegiatan", "divisi", "blok", "posting_date"]) {
            frappe.ui.form.on(doc.doctype, fieldname, function () {
                // me.get_rkh_data()
            });
        }

        for (const fieldname of ["qty_brondolan", "buah_tidak_dipanen", "buah_mentah_disimpan", "buah_mentah_ditinggal", "brondolan_tinggal",
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
        item.hari_kerja = doc.volume_basis ? flt(item.qty / doc.volume_basis) : 1

        item.rate = item.rate ?? doc.rupiah_basis
        item.brondolan = doc.upah_brondolan

        // perhitungan denda
        let buah_tidak_dipanen = flt(doc.buah_tidak_dipanen_rate * item.buah_tidak_dipanen) || 0.0
        let buah_mentah_disimpan = flt(doc.buah_mentah_disimpan_rate * item.buah_mentah_disimpan) || 0.0
        let buah_mentah_ditinggal = flt(doc.buah_mentah_ditinggal_rate * item.buah_mentah_ditinggal) || 0.0
        let brondolan_tinggal = flt(doc.brondolan_tinggal_rate * item.brondolan_tinggal) || 0.0
        let pelepah_tidak_disusun = flt(doc.pelepah_tidak_disusun_rate * item.pelepah_tidak_disusun) || 0.0
        let tangkai_panjang = flt(doc.tangkai_panjang_rate * item.tangkai_panjang) || 0.0
        let buah_tidak_disusun = flt(doc.buah_tidak_disusun_rate * item.buah_tidak_disusun) || 0.0
        let pelepah_sengkleh = flt(doc.pelepah_sengkleh_rate * item.pelepah_sengkleh) || 0.0


        item.brondolan_amount = flt(item.brondolan * item.qty_brondolan) || 0.0
        item.denda = flt(buah_tidak_dipanen + buah_mentah_disimpan + buah_mentah_ditinggal + brondolan_tinggal +
            pelepah_tidak_disusun + tangkai_panjang + buah_tidak_disusun + pelepah_sengkleh)
    }

    update_value_after_amount(item) {
        item.amount += item.brondolan_amount - item.denda
    }

    after_calculate_item_values(table_name, total) {
        // update nilai sebaran dan rotasi jika ada
        let data_table = this.frm.doc[table_name] || []
        let brondolan_qty = 0.0

        for (const item of data_table) {
            brondolan_qty += item.qty_brondolan || 0
        }

        this.frm.doc.brondolan_qty = brondolan_qty || 0;

        if (table_name == "hasil_kerja") {
            this.frm.doc.hari_kerja_total = flt(total["hari_kerja"]);
        }
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