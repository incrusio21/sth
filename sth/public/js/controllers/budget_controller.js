frappe.provide("sth.plantation");

sth.plantation = {
	setup_budget_controller: function() {
        sth.plantation.BudgetController = class BudgetController extends frappe.ui.form.Controller {
            setup(doc) {
                let doctype = doc.doctype
                // check daftar fieldname dengan total didalamny untuk d gabungkan ke grand_total
                if(!sth.plantation.doctype_ref[doctype]){
                    sth.plantation.setup_doctype_ref(doctype)
                }

                let me = this
                for (const month of sth.plantation.month) {
                    frappe.ui.form.on(doctype, `per_${month}`, function() {
                        // update sebaran di semua table
                        me.doctype_ref("table_fieldname").forEach(table_ref => {
                            for (const item of me.frm.doc[table_ref] || []) {
                                me.calculate_sebaran_values(item)
                            }
                        });

                        me.frm.refresh_fields();
                    });
                }
            }

            refresh(doc) {
                this.frm.set_query("budget_kebun_tahunan", function(doc){
                    if(!doc.company){
                        frappe.throw("Please Select Company First")
                    }

                    return{
                        filters: {
                            company: doc.company
                        }
                    }
                })
            }
            
            company(){
                this.frm.set_value("budget_kebun_tahunan", "")
            }

            qty(_, cdt, cdn){
                this.calculate_total(cdt, cdn)
            }

            rate(_, cdt, cdn){
                this.calculate_total(cdt, cdn)
            }
            
            // mempersingkat structur koding
            doctype_ref(dict){
                return sth.plantation.doctype_ref[this.frm.doc.doctype][dict]
            }

            calculate_total(cdt, cdn){
                let items = frappe.get_doc(cdt, cdn)
                
                this.calculate_item_values(items.parentfield);
                this.calculate_grand_total();

                this.frm.refresh_fields();
            }

            calculate_item_values(table_name){
                let total_amount = 0.0;

                for (const item of this.frm.doc[table_name] || []) {
                    item.amount = flt(item.rate * item.qty, precision("amount", item));
                    total_amount += item.amount;

                    this.calculate_sebaran_values(item)
                }
                
                this.frm.doc[`${table_name}_total`] = total_amount;
            }

            calculate_sebaran_values(item){
                // set nilai sebaran
                let total_sebaran = 0.0
                for (const month of sth.plantation.month) {
                    const percentField = `per_${month}`;
                    const amountField = `rp_${month}`;  // rp_jan, rp_feb, dst
                    
                    item[amountField] = flt(
                        item.amount * (this.frm.doc[percentField] / 100),
                        precision(amountField, item)
                    );
                    total_sebaran += item[amountField]
                }

                if(total_sebaran > item.amount){
                    frappe.throw("Distribution exceeds 100%. Please recheck your input.")
                }
            }

            calculate_grand_total(){
                let grand_total = 0.0
                for (const field of this.doctype_ref("table_fieldname")) {
                    grand_total += this.frm.doc[`${field}_total`] || 0;
                }

                this.frm.doc.grand_total = grand_total

                this.after_calculate_grand_total()
            }

            after_calculate_grand_total(){
                // set on child class if needed
            }

            get_blok_list(args, callback){
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
                        fieldname: "vlm",
                        in_list_view: 1,
                        read_only: 1,
                        disabled: 0,
                        label: __("Luas Areal")
                    },
                ]

                frappe.call({
                    method: "sth.plantation.utils.get_blok",
                    args: args,
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

            add_blok_in_table(args, blok_table, default_field={}){
                this.get_blok_list(args, (data) => {
                    let cur_grid = this.frm.fields_dict[blok_table].grid;
                    data.forEach(blok => {
                        let row = frappe.model.add_child(this.frm.doc, cur_grid.doctype, blok_table);
                        let ignore_fields = [
                            "name",
                            "idx",
                            "__checked"
                        ];

                        for (let key in blok) {
                            if (in_list(ignore_fields, key)) {
                                continue;
                            }

                            row[key] = blok[key];
                        }
                        
                        if (default_field){
                            $.each(default_field, (key, value) => {
                                row[key] = value
                            })
                        }

                    });

                    refresh_field(blok_table);
                })
            }

            clear_table(){
                for (const field_table of this.doctype_ref("table_fieldname")) {
                    this.frm.clear_table(field_table)
                    this.frm.doc[`total_${field_table}`] = 0;
                }

                this.calculate_grand_total();
                this.frm.refresh_fields();
            }
        }
    } 
}

sth.plantation.month = [
    'januari', 'februari', 'maret', 'april', 'mei', 'juni',
    'juli', 'agustus', 'september', 'oktober', 'november', 'desember'
];


// menyimpan fieldname yang di butuhkan (fieltype Table)
sth.plantation.doctype_ref = {}
sth.plantation.setup_doctype_ref = function (doctype) {
    let fields = frappe.get_doc("DocType", doctype).fields;
    sth.plantation.doctype_ref[doctype] = {
        "table_fieldname": []
    };
    
   fields.forEach(d => {
        if (d.fieldtype === "Table") {
            sth.plantation.doctype_ref[doctype].table_fieldname.push(d.fieldname);
        }
    });
}