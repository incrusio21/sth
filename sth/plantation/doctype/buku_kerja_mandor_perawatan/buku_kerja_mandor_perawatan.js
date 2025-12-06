// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

sth.plantation.setup_bkm_controller()

frappe.ui.form.on("Buku Kerja Mandor Perawatan", {
    refresh(frm) {

    },
    kategori_kegiatan(frm) {
        frm.set_value({"blok": "", "batch": ""})
    },
});

sth.plantation.BukuKerjaMandorPerawatan = class BukuKerjaMandorPerawatan extends sth.plantation.BKMController {
    setup(doc) {
        super.setup(doc)
               
        this.fieldname_total.push("premi_amount")
        this.kegiatan_fetch_fieldname.push("have_premi", "min_basis_premi", "rupiah_premi")
        this.max_qty_fieldname = { "hasil_kerja": "volume_basis" }
        
        this.get_data_rkh_field.push("batch")
        this.hasil_kerja_update_field.push("have_premi", "min_basis_premi", "rupiah_premi")

        this.setup_bkm(doc)
    }

    set_query_field() {
        super.set_query_field()

        this.frm.set_query("kategori_kegiatan", function () {
            return {
                filters: {
                    is_perawatan: 1
                }
            }
        })

        this.frm.set_query("kegiatan", function (doc) {
            return {
                filters: {
                    kategori_kegiatan: ["=", doc.kategori_kegiatan],
                    company: ["=", doc.company],
                }
            }
        })

        this.frm.set_query("item", "material", function (doc) {
            return {
                query: 'sth.controllers.queries.material_kegiatan_query',
                filters: {
                    kegiatan: ["=", doc.kegiatan],
                }
            }
        })

        for (const fieldname of ["mandor", "mandor1", "kerani"]) {
            this.frm.set_query(fieldname, function () {
                return {
                    query: "sth.controllers.queries.employee_designation_query",
                      filters: {
                        supervisi: "Agronomi"
                    }
                };
            });
        }

    }

    update_rate_or_qty_value(item) {
        if (item.parentfield != "hasil_kerja") return

        let doc = this.frm.doc
        
        item.rate = item.rate || this.frm.doc.rupiah_basis
        item.premi_amount = 0
        
        if (!self.manual_hk){
            item.hari_kerja = Math.min(flt(item.qty / doc.volume_basis), 1)
        }
        
        if (doc.have_premi && doc.persentase_premi && item.qty >= doc.min_basis_premi){
            item.premi_amount = doc.rupiah_premi
        }
    }

    update_value_after_amount(item) {
        item.sub_total = flt(item.amount) + flt(item.premi_amount)
    }
}

cur_frm.script_manager.make(sth.plantation.BukuKerjaMandorPerawatan);
