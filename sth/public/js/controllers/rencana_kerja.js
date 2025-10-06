// Copyright (c) 2025, DAS and Contributors
// MIT License. See license.txt

sth.plantation.setup_rencana_kerja_controller = function() {
    sth.plantation.RencanaKerjaController = class RencanaKerjaController extends sth.plantation.TransactionController {
        setup(doc) {
            super.setup(doc)
            this.update_field_duplicate = []
            this.block_fieldname = []
            this.fieldname_duplicate_edit = []
            
            let me = this
            for (const fieldname of ["upah_mandor", "premi_mandor", "upah_kerani", 
                    "premi_kerani", "upah_mandor1", "premi_mandor1"
                ]) {
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
                    me.get_blok_for_duplicate()
                })
            }
        }

        set_query_field(){
            super.set_query_field()
        
            this.frm.set_query("blok", function(doc){
                if(!doc.divisi){
                    frappe.throw("Please Select Divisi First")
                }

                return{
                    filters: {
                        divisi: doc.divisi
                    }
                }
            })

        }

        update_value_after_amount(item){
           item.amount = flt(item.amount + (item.budget_tambahan || 0), precision("amount", item));
        }

        calculate_non_table_values(){
            let doc = this.frm.doc
            doc.mandor_amount = flt(doc.upah_mandor)  + flt(doc.premi_mandor)
            doc.kerani_amount = flt(doc.upah_kerani) + flt(doc.premi_kerani)
            doc.mandor1_amount = flt(doc.upah_mandor1) + flt(doc.premi_mandor1)
            this.calculate_amount_addons()
        }

        calculate_amount_addons(){
            // set on child class if needed
        }
        
        get_blok_for_duplicate(){
            let me = this
            
            me.get_blok_list({ 
                method: "sth.controllers.rencana_kerja_controller.get_not_used_blok",
                fields: this.update_field_duplicate,
                args: {
                    doctype: me.frm.doc.doctype, 
                    filters: {
                        divisi: me.frm.doc.divisi
                    }, 
                    fieldname: this.block_fieldname,
                }
            }, (data) => {
                frappe.call({
                    method: "sth.controllers.rencana_kerja_controller.duplicate_rencana_kerja",
                    args: {
                        voucher_type: me.frm.doc.doctype,
                        voucher_no: me.frm.doc.name,
                        blok: data,
                        fieldname_addons: this.fieldname_duplicate_edit || 
                            Object.fromEntries(this.update_field_duplicate.map(key => [key, key]))
                    },
                })
            })
        }
    }
}