// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

sth.plantation.setup_rencana_kerja_controller()

frappe.ui.form.on("Rencana Kerja Bulanan Perawatan", {
	refresh(frm) {
        
	},
    
});

sth.plantation.RencanaKerjaBulananPerawatan = class RencanaKerjaBulananPerawatan extends sth.plantation.RencanaKerjaController {
    setup(doc) {
        super.setup(doc)

        let me = this
        for (const fieldname of ["qty_basis", "upah_per_basis", "premi"]) {
            frappe.ui.form.on(doc.doctype, fieldname, function(doc, cdt, cdn) {
                me.calculate_total(cdt, cdn)
            });
        }
    }

    refresh(){
        super.refresh()

        let me = this
        if(me.frm.doc.docstatus == 1){
            this.frm.add_custom_button("Duplicate", function(){
                me.get_blok_list({ 
                    method: "sth.controllers.rencana_kerja_controller.get_not_used_blok",
                    args: {
                        doctype: me.frm.doc.doctype, 
                        filters: {
                            divisi: me.frm.doc.divisi
                        }, 
                    }
                }, (data) => {
                    frappe.call({
                        method: "sth.controllers.rencana_kerja_controller.duplicate_rencana_kerja",
                        args: {
                            voucher_type: me.frm.doc.doctype,
                            voucher_no: me.frm.doc.name,
                            blok: data.map((d) => d.item)
                        },
                    })
                })
            })
        }
    }

    set_query_field(){
        super.set_query_field()
    
        this.frm.set_query("kode_kegiatan", function(doc){
            return{
                filters: {
                    is_group: 0
                }
            }
        })

    }
    
    calculate_total(cdt, cdn, parentfield=null){
        let doc = this.frm.doc
        if(!parentfield){
            parentfield = frappe.get_doc(cdt, cdn).parentfield
        }
        
        if(parentfield){
            this.calculate_item_values(parentfield, ["budget_tambahan"]);
        }else {
            doc.jumlah_tenaga_kerja = doc.qty_basis ? flt(doc.qty / doc.qty_basis) : 0
            doc.amount = flt(doc.jumlah_tenaga_kerja * doc.upah_per_basis) + flt(doc.premi)
        }

        this.calculate_grand_total();

        this.frm.refresh_fields();
    }
}

cur_frm.script_manager.make(sth.plantation.RencanaKerjaBulananPerawatan);