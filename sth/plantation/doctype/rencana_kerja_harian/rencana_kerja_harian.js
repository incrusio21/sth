// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Rencana Kerja Harian", {
    refresh(frm) {
        frm.set_df_property("material", "cannot_add_rows", true);
        frm.set_df_property("kendaraan", "cannot_add_rows", true);
        frm.set_df_property("angkut", "cannot_add_rows", true);
    }
});

sth.plantation.RencanaKerjaHarian = class RencanaKerjaHarian extends sth.plantation.TransactionController {
    setup(doc) {
        super.setup(doc)

        // basis upah sekarang tinggal di tiap baris kegiatan, bukan di dokumen,
        // jadi tidak ada lagi yang perlu diambil ke level dokumen
        this.kegiatan_fetch_fieldname = []
    }

    kegiatan(doc, cdt, cdn) {
        let row = locals[cdt][cdn]
        if (!row || row.parentfield != "kegiatan_detail") return

        frappe.model.set_value(cdt, cdn, { blok: "", batch: "" })

        if (!row.kegiatan) {
            frappe.model.set_value(cdt, cdn, { volume_basis: 0, rupiah_basis: 0 })
            this.calculate_total(cdt, cdn)
            return
        }

        this.fetch_basis_kegiatan(cdt, cdn)
    }

    target_volume(_, cdt, cdn) {
        this.hitung_kegiatan_dan_material(cdt, cdn)
    }

    qty_tenaga_kerja(_, cdt, cdn) {
        this.hitung_kegiatan_dan_material(cdt, cdn)
    }

    jumlah_tk_laki_laki(_, cdt, cdn) {
        this.isi_tenaga_kerja_dari_rincian(cdt, cdn)
    }

    jumlah_tk_perempuan(_, cdt, cdn) {
        this.isi_tenaga_kerja_dari_rincian(cdt, cdn)
    }

    blok(_, cdt, cdn) {
        let row = locals[cdt][cdn]
        if (!row || row.parentfield != "kegiatan_detail") return

        // material dari form ditambahkan waktu kegiatannya dipilih, sebelum ada
        // bloknya; begitu blok terisi atau diganti, material yang belum punya blok
        // atau bloknya tidak ada lagi di tabel kegiatan ikut menunjuk blok ini
        let baris = this.frm.doc.kegiatan_detail || []
        for (const m of this.frm.doc.material || []) {
            if (m.kegiatan != row.kegiatan) continue

            let yatim = !baris.some(r => r.kegiatan == m.kegiatan && r.blok == m.blok)
            if (!m.blok || yatim) m.blok = row.blok
        }

        this.frm.refresh_field("material")
    }

    kegiatan_detail_remove() {
        // material milik baris kegiatan yang dihapus ikut dibuang
        let baris = this.frm.doc.kegiatan_detail || []
        this.frm.doc.material = (this.frm.doc.material || []).filter(m =>
            !m.kegiatan || baris.some(r => r.kegiatan == m.kegiatan && (!m.blok || r.blok == m.blok))
        )
        this.frm.doc.material.forEach((m, i) => m.idx = i + 1)
        this.frm.refresh_field("material")

        this.hitung_kegiatan_dan_material(null, null)
    }

    dosis(_, cdt, cdn) {
        this.calculate_total(cdt, cdn)
    }

    set_query_field() {
        super.set_query_field()

        this.frm.set_query("blok", "kegiatan_detail", function (doc) {
            if (!doc.divisi) {
                frappe.throw(__("Please Select Divisi First"))
            }

            return {
                filters: {
                    divisi: doc.divisi,
                }
            }
        })

        this.frm.set_query("kegiatan", "kegiatan_detail", function (doc) {
            return {
                filters: {
                    company: ["=", doc.company],
                }
            }
        })
    }

    // Luas pekerjaan menentukan qty tiap baris material, jadi tabel material ikut
    // dihitung ulang tiap kali baris kegiatan berubah.
    hitung_kegiatan_dan_material(cdt, cdn) {
        this.calculate_total(cdt, cdn, "kegiatan_detail")
        this.calculate_total(null, null, "material")
    }

    isi_tenaga_kerja_dari_rincian(cdt, cdn) {
        let row = locals[cdt][cdn]
        let rincian = cint(row.jumlah_tk_laki_laki) + cint(row.jumlah_tk_perempuan)

        if (rincian) {
            frappe.model.set_value(cdt, cdn, "qty_tenaga_kerja", rincian)
            return
        }

        this.hitung_kegiatan_dan_material(cdt, cdn)
    }

    fetch_basis_kegiatan(cdt, cdn) {
        let me = this
        let row = locals[cdt][cdn]

        frappe.call({
            method: "sth.controllers.plantation_controller.fetch_kegiatan_company",
            args: {
                kegiatan: row.kegiatan,
                company: me.frm.doc.company,
                unit: me.frm.doc.unit,
                fieldname: ["volume_basis", "rupiah_basis"],
            },
            callback: function (data) {
                frappe.model.set_value(cdt, cdn, data.message || { volume_basis: 0, rupiah_basis: 0 })
                me.tambah_material_kegiatan(row)
                me.hitung_kegiatan_dan_material(cdt, cdn)
            }
        })
    }

    tambah_material_kegiatan(row) {
        let me = this

        frappe.call({
            method: "sth.plantation.doctype.rencana_kerja_harian.rencana_kerja_harian.get_material",
            args: { kode_kegiatan: row.kegiatan },
            callback: function (data) {
                // ditambahkan, bukan menimpa: satu RKH memuat beberapa kegiatan, dan
                // tiap baris material menunjuk kegiatan pemiliknya
                let kunci = d => [d.item, d.kegiatan, d.blok || ""].join("|")
                let sudah_ada = (me.frm.doc.material || []).map(kunci)

                for (const m of (data.message || {}).material || []) {
                    let baru = { ...m, kegiatan: row.kegiatan, blok: row.blok }
                    if (sudah_ada.includes(kunci(baru))) continue

                    me.frm.add_child("material", baru)
                    sudah_ada.push(kunci(baru))
                }

                me.frm.refresh_field("material")
                me.calculate_total(null, null, "material")
            }
        })
    }

    update_rate_or_qty_value(item) {
        if (item.parentfield == "kegiatan_detail") {
            item.rate = flt(item.rupiah_basis)
            item.qty = item.tipe_kegiatan == "Panen" ? flt(item.target_volume) : cint(item.qty_tenaga_kerja)
        }

        if (item.parentfield == "material") {
            // sama dengan server: dibagi luas baris pemiliknya, atau total luas
            // kalau materialnya tidak menunjuk kegiatan
            let pemilik = item.kegiatan && (this.frm.doc.kegiatan_detail || []).find(r =>
                r.kegiatan == item.kegiatan && (r.blok || "") == (item.blok || "")
                && (r.batch || "") == (item.batch || "")
            )
            let luas = pemilik ? flt(pemilik.target_volume) : flt(this.frm.doc.total_luas)
            item.qty = luas ? flt(item.dosis / luas) : 0
        }
    }

    after_calculate_item_values(table_name) {
        if (table_name != "kegiatan_detail") return

        let baris = this.frm.doc.kegiatan_detail || []

        this.frm.doc.total_luas = baris.reduce((t, d) => t + flt(d.target_volume), 0)
        this.frm.doc.total_tenaga_kerja = baris.reduce((t, d) => t + cint(d.qty_tenaga_kerja), 0)
        this.frm.doc.total_tk_laki_laki = baris.reduce((t, d) => t + cint(d.jumlah_tk_laki_laki), 0)
        this.frm.doc.total_tk_perempuan = baris.reduce((t, d) => t + cint(d.jumlah_tk_perempuan), 0)
    }
}

cur_frm.script_manager.make(sth.plantation.RencanaKerjaHarian);
