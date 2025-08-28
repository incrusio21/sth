// Copyright (c) 2025, DAS and Contributors
// MIT License. See license.txt

frappe.provide("sth.plantation");

sth.plantation.TransactionController = class TransactionController extends frappe.ui.form.Controller {
    setup(doc) {
        let doctype = doc.doctype
        this.skip_table_amount = []
        this.skip_fieldname_amount = []
        // check daftar fieldname dengan total didalamny untuk d gabungkan ke grand_total
        if(!sth.plantation.doctype_ref[doctype]){
            sth.plantation.setup_doctype_ref(doctype)
        }
    }

    refresh() {
        this.set_query_field()
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
    
    qty(_, cdt, cdn){
        this.calculate_total(cdt, cdn)
    }

    rate(_, cdt, cdn){
        this.calculate_total(cdt, cdn)
    }
    
    rotasi(_, cdt, cdn){
        this.calculate_total(cdt, cdn)
    }

    // mempersingkat structur koding
    doctype_ref(dict){
        return sth.plantation.doctype_ref[this.frm.doc.doctype][dict]
    }

    set_query_field(){
        this.frm.set_query("divisi", function(doc){
            return{
                filters: {
                    unit: doc.unit
                }
            }
        })
    }

    calculate_total(cdt, cdn, parentfield=null){
        if(!parentfield){
            parentfield = frappe.get_doc(cdt, cdn).parentfield
        }
        
        this.calculate_item_values(parentfield);
        this.calculate_grand_total();

        this.frm.refresh_fields();
    }

    calculate_item_values(table_name, field_tambahan=[]){
        let me = this
        let total = {"amount": 0, "qty": 0, "rotasi": 0}
        let total_rotasi = 0.0
        let data_table = me.frm.doc[table_name] || []
        
        // menghitung amount, rotasi, qty
        for (const item of data_table) {
            // rate * qty * (rotasi jika ada)
            item.amount = flt(item.rate * item.qty * (item.rotasi || 1), precision("amount", item));
            for (const fieldname of field_tambahan){
                item.amount += item[fieldname] || 0
            }

            total["amount"] += item.amount;
            total["qty"] += item.qty
            total_rotasi += item.rotasi || 0
        }
        
        total["rotasi"] = total_rotasi / data_table.length;
        
        for (const total_field of ["amount", "qty", "rotasi"]) {
            let fieldname = `${table_name}_${total_field}`
            if (!this.frm.fields_dict[fieldname]) continue;

            this.frm.doc[fieldname] = total[total_field];
        }

        this.after_calculate_item_values(table_name)
    }

    calculate_grand_total(){
        let grand_total = 0.0
        for (const field of this.doctype_ref("amount")) {
            if(in_list(this.skip_table_amount, field.replace("_amount", "")) || 
                in_list(this.skip_fieldname_amount, field)) continue;
            
            grand_total += this.frm.doc[field] || 0;
        }

        this.frm.doc.grand_total = grand_total

        this.after_calculate_grand_total()
    }

    after_calculate_grand_total(){
        // set on child class if needed
    }

    after_calculate_grand_total(){
        // set on child class if needed
    }
    
    get_blok_list(opts, callback){
        const fields = [
            {
                fieldtype: "Link",
                fieldname: "item",
                options: "Blok",
                in_list_view: 1,
                read_only: 1,
                disabled: 0,
                label: __("Blok")
            },
            {
                fieldtype: "Int",
                fieldname: "tahun_tanam",
                in_list_view: 1,
                read_only: 1,
                disabled: 0,
                label: __("Tahun Tanam")
            },
            {
                fieldtype: "Int",
                fieldname: "luas_areal",
                in_list_view: 1,
                read_only: 1,
                disabled: 0,
                label: __("Luas Areal")
            },
        ]

        fields.push(
            {
                fieldtype: "Int",
                fieldname: "sph",
                in_list_view: 1,
                read_only: 1,
                label: __("SPH")
            },
            {
                fieldtype: "Int",
                fieldname: "jumlah_pokok",
                in_list_view: 1,
                read_only: 1,
                label: __("Jumlah Pokok")
            },
        )

        frappe.call({
            method: opts.method || "sth.plantation.utils.get_blok",
            args: {
                args: opts.args
            },
            freeze: true,
            callback: function (data) {
                if (data.message.length == 0) {
                    frappe.throw(__("Blok Not Found."))
                }
                
                const dialog = new frappe.ui.Dialog({
                    title: __("Select Blok"),
                    fields: [
                        {
                            fieldname: "trans_blok",
                            fieldtype: "Table",
                            label: "Items",
                            cannot_add_rows: 1,
                            cannot_delete_rows: 1,
                            in_place_edit: false,
                            reqd: 1,
                            get_data: () => {
                                return data.message;
                            },
                            fields: fields,
                        }
                    ],
                    primary_action: function () {
                        const selected_items = dialog.fields_dict.trans_blok.grid.get_selected_children();
                        if(selected_items.length < 1){
                            frappe.throw("Please Select at least One Blok")
                        }

                        callback && callback(selected_items)
                        dialog.hide();
                    },
                    primary_action_label: __("Submit"),
                });
        
                dialog.show();
            }
        })
    }
}


// menyimpan fieldname yang di butuhkan (fieltype Table)
sth.plantation.doctype_ref = {}
sth.plantation.setup_doctype_ref = function (doctype) {
    let fields = frappe.get_doc("DocType", doctype).fields;
    sth.plantation.doctype_ref[doctype] = {
        "amount": [],
        "table_fieldname": []
    };
    
   fields.forEach(d => {
        if (d.fieldtype === "Currency" && in_list(d.fieldname, "amount")) {
            sth.plantation.doctype_ref[doctype].amount.push(d.fieldname);
        }

        if (d.fieldtype === "Table") {
            sth.plantation.doctype_ref[doctype].table_fieldname.push(d.fieldname);
        }
    });
}