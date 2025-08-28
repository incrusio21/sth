// Copyright (c) 2025, DAS and Contributors
// MIT License. See license.txt

sth.plantation.setup_rencana_kerja_controller = function() {
    sth.plantation.RencanaKerjaController = class RencanaKerjaController extends sth.plantation.TransactionController {
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
    }
}