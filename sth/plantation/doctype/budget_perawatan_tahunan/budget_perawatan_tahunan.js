// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

sth.plantation.setup_budget_controller()

frappe.ui.form.on("Budget Perawatan Tahunan", {
    divisi(frm){
        frm.cscript.clear_table(["upah_perawatan", "upah_bibitan"])

        // jika kegiatan bibitan skip popup
        if(frm.doc.is_bibitan || !frm.doc.divisi) return

        frm.cscript.add_blok_in_table("upah_perawatan",
            { divisi: frm.doc.divisi }, 
            { "uom": frm.doc.uom }
        )
    }
});

frappe.ui.form.on("Detail Budget Upah Perawatan", {
	item(frm, cdt, cdn){
        frappe.model.set_value(cdt, cdn, "uom", frm.doc.uom)
    }
});

sth.plantation.BudgetPerawatanTahunan = class BudgetPerawatanTahunan extends sth.plantation.BudgetController {
    setup(doc) {
        super.setup(doc)
        this.fieldname_total.push("qty", "rotasi")
    }
    set_query_field(){
        super.set_query_field()

        this.frm.set_query("kategori_kegiatan", function(){
		    return{
		        filters: {
                    is_perawatan: 1
                }
		    }
		})

        this.frm.set_query("divisi", function(doc){
            if(!doc.kategori_kegiatan){
                frappe.throw("Please Select Kategori Kegiatan First")
            }

            return{
		        filters: {
                    unit: doc.unit
                }
		    }
		})

        this.frm.set_query("kegiatan", function(doc){
            if(!doc.kategori_kegiatan){
                frappe.throw("Please Select Kategori Kegiatan First")
            }

		    return{
		        filters: {
                    is_group: 0,
                    kategori_kegiatan: doc.kategori_kegiatan,
                    company: doc.company
                }
		    }
		})

        this.frm.set_query("item", "upah_perawatan", function(doc){
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

        // frm.set_query("item", "peralatan", function(doc){

		// })

        this.frm.set_query("item", "transport", function(doc){
            if(!doc.divisi){
                frappe.throw("Please Select Divisi First")
            }
		    return{
		        filters: {
                    unit: doc.unit
                }
		    }
		})
    }
    
    kategori_kegiatan(){
        this.frm.set_value("kegiatan", "")
        this.frm.set_value("divisi", "")
        this.clear_table(["upah_perawatan", "upah_bibitan"])
    }

    after_calculate_item_values(table_name, total){
        super.after_calculate_item_values(table_name, total)
        
        let data_table = this.frm.doc[table_name] || []
        this.frm.doc[`mean_${table_name}_rotasi`] = flt(total["rotasi"] / data_table.length) || 0;
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