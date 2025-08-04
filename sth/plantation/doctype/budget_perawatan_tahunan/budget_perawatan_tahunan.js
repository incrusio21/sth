// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

sth.plantation.setup_budget_controller()

frappe.ui.form.on("Budget Perawatan Tahunan", {
	refresh(frm) {
        frm.trigger("set_query_field");
	},
    set_query_field(frm){
        frm.set_query("kategori_kegiatan", function(){
		    return{
		        filters: {
                    is_perawatan: 1
                }
		    }
		})

        frm.set_query("divisi", function(doc){
            if(!doc.kategori_kegiatan){
                frappe.throw("Please Select Kategori Kegiatan First")
            }

            return{
		        filters: {
                    unit: doc.unit
                }
		    }
		})

        frm.set_query("kegiatan", function(doc){
            if(!doc.kategori_kegiatan){
                frappe.throw("Please Select Kategori Kegiatan First")
            }

		    return{
		        filters: {
                    is_group: 0,
                    kategori_kegiatan: doc.kategori_kegiatan
                }
		    }
		})

        frm.set_query("item", "upah_perawatan", function(doc){
            if(!(doc.kegiatan && doc.divisi)){
                frappe.throw("Please Select Kegiatan and Divisi First")
            }

		    return{
		        filters: {
                    divisi: doc.divisi,
                    disabled: 0
                }
		    }
		})

        frm.set_query("item", "peralatan", function(doc){
		    return{
		        filters: {
                    tipe: "Alat"
                }
		    }
		})

        frm.set_query("item", "transport", function(doc){
		    return{
		        filters: {
                    tipe: "Kendaraan"
                }
		    }
		})
    }
});

frappe.ui.form.on("Detail Budget Upah Perawatan", {
	item(frm, cdt, cdn){
        frappe.model.set_value(cdt, cdn, "uom", frm.doc.uom)
    }
});

sth.plantation.BudgetPerawatanTahunan = class BudgetPerawatanTahunan extends sth.plantation.BudgetController {
    refresh(doc) {
        super.refresh(doc)
	}

    item(doc, cdt, cdn){
        let data = frappe.get_doc(cdt, cdn)
        let doctype = this.frm.fields_dict[data.parentfield].grid.fields_map.item.options;

        frappe.call({
            method: "sth.plantation.utils.get_rate_item",
            args: {
                item: data.item,
                doctype: doctype,
                company: doc.company
            },
            freeze: true,
            callback: function (data) {
                frappe.model.set_value(cdt, cdn, "rate", data.message.rate)
            }
        })
    }

    kategori_kegiatan(){
        this.frm.set_value("kegiatan", "")
        this.frm.set_value("divisi", "")
        this.clear_table()
    }

    rotasi(_, cdt, cdn){
        let items = frappe.get_doc(cdt, cdn)
        
        let table_name = this.frm.doc[items.parentfield] || []
        let mean_rotasi = 0.0
        
        for (const item of table_name) {
           mean_rotasi += item.rotasi
        }

        this.frm.set_value("mean_rotasi", flt(mean_rotasi/table_name.length, precision("mean_rotasi", this.frm.doc)))
    }

    divisi(doc){
        this.clear_table()

        // jika kegiatan bibitan skip popup
        if(doc.is_bibitan || !doc.divisi) return

        this.add_blok_in_table({ divisi: doc.divisi }, 
            "upah_perawatan", 
            { "uom": doc.uom }
        )
    }

    after_calculate_grand_total(){
        // tambah volume total dari table upah bibitan/perawatan
        let table_field = this.frm.doc.is_bibitan ? "upah_bibitan" : "upah_perawatan"
        let table_name = this.frm.doc[table_field] || []
		let volume_total = 0.0
        let mean_rotasi = 0.0

        for (const item of table_name) {
           volume_total += item.qty
           mean_rotasi += item.rotasi
        }

		this.frm.doc.volume_total = volume_total
		this.frm.doc.mean_rotasi = flt(mean_rotasi / table_name.length, precision("mean_rotasi", this.frm.doc))
        this.frm.doc.ha_per_tahun = flt(this.frm.doc.grand_total / this.frm.doc.volume_total, precision("ha_per_tahun", this.frm.doc));
    }
}

cur_frm.script_manager.make(sth.plantation.BudgetPerawatanTahunan);