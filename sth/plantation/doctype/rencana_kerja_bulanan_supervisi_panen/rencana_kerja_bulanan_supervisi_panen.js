// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Rencana Kerja Bulanan Supervisi Panen", {
// 	refresh(frm) {
        
// 	},
// });

sth.plantation.RencanaKerjaBulananSupervisiPanen = class RencanaKerjaBulananSupervisiPanen extends frappe.ui.form.Controller {
    refresh() {
        this.set_query_field()
    }

    set_query_field() {
        this.frm.set_query("divisi", "details", function(doc){
            return{
                filters: {
                    unit: doc.unit,
                }
            }
        })
    }

    rencana_kerja_bulanan(){
        this.frm.clear_table("details")

        this.frm.refresh_fields();
    }

    divisi(doc, cdt, cdn){
        frappe.call({
            method: "sth.controllers.rencana_kerja_controller.get_tonase",
            frezee: true,
            args: {
                rkb: doc.rencana_kerja_bulanan,
                filters: {
                    divisi: doc.divisi,
                }
            },
            callback: function (data) {
                frappe.model.set_value(cdt, cdn, "tonase", data.message)
            }
        })
    }
}

cur_frm.script_manager.make(sth.plantation.RencanaKerjaBulananSupervisiPanen);
