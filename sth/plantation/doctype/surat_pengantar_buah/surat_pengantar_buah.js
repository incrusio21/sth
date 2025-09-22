// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Surat Pengantar Buah", {
// 	refresh(frm) {

// 	},
// });

sth.plantation.SuratPengantarBuah = class SuratPengantarBuah extends frappe.ui.form.Controller {
    refresh() {
        this.set_query_field()
        let me = this

        for (const fieldname of ["blok", "panen_date"]) {
            frappe.ui.form.on("SPB Timbangan Pabrik", fieldname, function(frm, cdt, cdn) {
                let items = locals[cdt][cdn]
                me.get_bkm_panen_data(items)
            });
        }

        if(me.frm.doc.docstatus == 1){
            this.frm.add_custom_button("Update Timbangan", function(){
                me.set_timbangan()
            })
        }
    }

    set_query_field(){
        this.frm.set_query("unit", function(doc){
            if(!doc.company){
                frappe.throw("Please Select Company First")
            }
            
            return{
                filters: {
                    company: doc.company
                }
            }
        })

        this.frm.set_query("divisi", function(doc){
            if(!doc.unit){
                frappe.throw("Please Select Unit/Kebun First")
            }
            
            return{
                filters: {
                    unit: doc.unit
                }
            }
        })

        this.frm.set_query("kendaraan", function(doc){
            if(!doc.divisi){
                frappe.throw("Please Select Divisi First")
            }
            
            return{
                filters: {
                    divisi: doc.divisi
                }
            }
        })

        this.frm.set_query("blok", "details", function(doc){
            if(!doc.unit){
                frappe.throw("Please Select Unit First")
            }
            
            return{
                filters: {
                    unit: doc.unit
                }
            }
        })
    }

    get_bkm_panen_data(item){
        let me = this

        if(!(item.blok && item.panen_date)) return
        
        frappe.call({
            method: "sth.plantation.doctype.surat_pengantar_buah.surat_pengantar_buah.get_bkm_panen",
            args: {
                blok: item.blok,
                posting_date: item.panen_date
            },
            freeze: true,
            callback: function (data) {
                frappe.model.set_value(item.doctype, item.name, data.message)
            }
        })
    }

    set_timbangan(){
        let me = this
        let doc = this.frm.doc
        
        let fields = [
            {
                fieldtype: "Time",
                fieldname: "in_time",
                disabled: 0,
                reqd: 1,
                label: __("In Time"),
                default: doc.in_time
            },
            {
                fieldtype: "Float",
                fieldname: "in_weight",
                disabled: 0,
                reqd: 1,
                label: __("In Weight"),
                default: doc.in_weight
            },
            {
                fieldtype: "Column Break",
            },
            {
                fieldtype: "Time",
                fieldname: "out_time",
                disabled: 0,
                reqd: 1,
                label: __("Out Time"),
                default: doc.out_time
            },
            {
                fieldtype: "Float",
                fieldname: "out_weight",
                disabled: 0,
                reqd: 1,
                label: __("Out Weight"),
                default: doc.out_weight
            },
        ]

        if(doc.pabrik_type == "External"){
            fields.push({
                fieldtype: "Float",
                fieldname: "pabrik_cut",
                disabled: 0,
                reqd: 1,
                label: __("Potongan Pabrik"),
                default: doc.pabrik_cut
            })
        }

        const dialog = new frappe.ui.Dialog({
            title: __("Set Timbangan"),
            fields: fields,
            primary_action: function (data) {
                frappe.call({
                    method: "set_pabrik_weight",
                    doc: doc,
                    args: {
                        ...data
                    },
                    freeze: true,
                    callback: function () {
                        dialog.hide();
                        me.frm.refresh_fields()
                    }
                })
            },
            primary_action_label: __("Submit"),
        });

        dialog.show();
    }
}
cur_frm.script_manager.make(sth.plantation.SuratPengantarBuah);