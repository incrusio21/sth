// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Rencana Kerja Bulanan Supervisi Panen", {
// 	refresh(frm) {
        
// 	},
// });

sth.plantation.RencanaKerjaBulananSupervisiPanen = class RencanaKerjaBulananSupervisiPanen extends frappe.ui.form.Controller {
    refresh() {
        this.frm.set_df_property("details", "cannot_add_rows", true);
        this.frm.set_df_property("details", "cannot_delete_rows", true);

        this.set_query_field()
    }

    set_query_field() {
        this.frm.set_query("divisi", function(doc){
            return{
                filters: {
                    unit: doc.unit,
                }
            }
        })
    }

    divisi(doc){
        let me = this
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
                me.frm.set_value("total_tonase", data.message)
            }
        })
    }
}

cur_frm.script_manager.make(sth.plantation.RencanaKerjaBulananSupervisiPanen);
