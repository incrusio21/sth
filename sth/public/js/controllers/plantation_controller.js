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

    calculate_grand_total(){
        let grand_total = 0.0
        console.log(this.doctype_ref("amount"))
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