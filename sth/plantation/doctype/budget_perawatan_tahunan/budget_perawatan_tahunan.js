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
        this.clear_table(["upah_perawatan", "upah_bibitan"])
    }

    divisi(doc){
        this.clear_table(["upah_perawatan", "upah_bibitan"])

        // jika kegiatan bibitan skip popup
        if(doc.is_bibitan || !doc.divisi) return

        this.add_blok_in_table({ divisi: doc.divisi }, 
            "upah_perawatan", 
            { "uom": doc.uom }
        )
    }

    after_calculate_grand_total(){
        // biaya per tahun = grand total / qty table bibitan atau perawatan
        let table_name = this.frm.doc.is_bibitan ? "upah_bibitan" : "upah_perawatan"
        this.frm.doc.ha_per_tahun = flt(
            this.frm.doc.grand_total / this.frm.doc[`${table_name}_qty`], 
            precision("ha_per_tahun", this.frm.doc)
        );
    }
}

cur_frm.script_manager.make(sth.plantation.BudgetPerawatanTahunan);