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
                me.get_recap_panen_data(items, "blok", "panen_date")
            });
        }

        for (const fieldname of ["blok_restan", "panen_date_restan"]) {
            frappe.ui.form.on("SPB Timbangan Pabrik", fieldname, function(frm, cdt, cdn) {
                let items = locals[cdt][cdn]
                me.get_recap_panen_data(items, "blok_restan", "panen_date_restan", true)
            });
        }

        if(me.frm.doc.docstatus == 1 && me.frm.doc.workflow_state != "Weighed"){
            const { pabrik_type } = me.frm.doc;

            me.frm.add_custom_button("Mill", () => me.set_timbangan(), "Weighbridge");

            // Internal In/Out
            if (pabrik_type == "External") {
                me.frm.add_custom_button("Internal", () => me.set_timbangan("_internal"), "Weighbridge");
            }
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

            return{
                filters: {
                    unit: ["=",doc.unit]
                }
            }
        })

        this.frm.set_query("blok", "details", function(doc){
            if(!doc.unit){
                frappe.throw("Please Select Unit First")
            }
            
            return{
                filters: {
                    unit: ["=", doc.unit],
                    divisi: ["=", doc.divisi],
                }
            }
        })

        this.frm.set_query("blok_restan", "details", function(doc){
            return{
                filters: {
                    unit: ["=", doc.unit],
                    divisi: ["=", doc.divisi],
                }
            }
        })
    }

    get_recap_panen_data(item, blok_fieldname, date_fieldname, restan=false){
        let me = this
        let restan_field = restan ? "_restan" : ""

        if(!(item[blok_fieldname] && item[date_fieldname])) return
        
        frappe.call({
            method: "sth.plantation.doctype.surat_pengantar_buah.surat_pengantar_buah.get_recap_panen",
            args: {
                blok: item[blok_fieldname],
                posting_date: item[date_fieldname],
                status: !restan
            },
            freeze: true,
            callback: function (r) {
                $.each(r.message, function(k, v) {
                    item[k + restan_field] = v;
                });

                me.frm.refresh_fields("items")
            }
        })
    }

    set_timbangan(tipe_timbangan=""){
        let me = this
        let doc = this.frm.doc

        let fields = [
            {
                fieldtype: "Time",
                fieldname: `in_time${tipe_timbangan}`,
                disabled: 0,
                reqd: 1,
                label: __(`In Time`),
                default: doc.in_time
            },
            {
                fieldtype: "Float",
                fieldname: `in_weight${tipe_timbangan}`,
                disabled: 0,
                reqd: 1,
                label: __(`In Weight (Kg)`),
                default: doc.in_weight
            },
            {
                fieldtype: "Column Break",
            },
            {
                fieldtype: "Time",
                fieldname: `out_time${tipe_timbangan}`,
                disabled: 0,
                reqd: 1,
                label: __(`Out Time`),
                default: doc.out_time
            },
            {
                fieldtype: "Float",
                fieldname: `out_weight${tipe_timbangan}`,
                disabled: 0,
                reqd: 1,
                label: __(`Out Weight (Kg)`),
                default: doc.out_weight
            }
        ]

        if(!tipe_timbangan && doc.pabrik_type == "External"){
            fields.push({
                fieldtype: "Float",
                fieldname: "mill_cut",
                disabled: 0,
                reqd: 1,
                label: __("Mill Cut"),
                default: doc.mill_cut
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