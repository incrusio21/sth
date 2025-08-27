// Copyright (c) 2025, DAS and Contributors
// MIT License. See license.txt

sth.plantation.month = [
    'januari', 'februari', 'maret', 'april', 'mei', 'juni',
    'juli', 'agustus', 'september', 'oktober', 'november', 'desember'
];

sth.plantation.setup_budget_controller = function() {
    sth.plantation.BudgetController = class BudgetController extends sth.plantation.TransactionController {
        setup(doc) {
            super.setup(doc)

            let me = this
            for (const month of sth.plantation.month) {
                frappe.ui.form.on(doc.doctype, `per_${month}`, function() {
                    // update sebaran di semua table
                    me.doctype_ref("table_fieldname").forEach(table_ref => {
                        let per_month_table = Object.keys(
                            me.frm.fields_dict[table_ref].grid.fields_map
                        ).filter(key => key.includes("rp_"));
                        // jika tidak ada fieldname degan kata per_ skip sebaran

                        if(per_month_table.length == 0) return
                        
                        for (const item of me.frm.doc[table_ref] || []) {
                            me.calculate_sebaran_values(item, per_month_table)
                        }
                    });

                    me.frm.refresh_fields();
                });
            }
        }
        
        set_query_field(){
            super.set_query_field()
        
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

        calculate_total(cdt, cdn, parentfield=null){
            if(!parentfield){
                parentfield = frappe.get_doc(cdt, cdn).parentfield
            }
            
            this.calculate_item_values(parentfield);
            this.calculate_grand_total();

            this.frm.refresh_fields();
        }

        calculate_item_values(table_name){
            let me = this
            let total = {"amount": 0, "qty": 0, "rotasi": 0}
            let total_rotasi = 0.0
            let data_table = me.frm.doc[table_name] || []
            
            let per_month_table = Object.keys(
                me.frm.fields_dict[table_name].grid.fields_map
            ).filter(key => key.includes("rp_"));
            
            // menghitung amount, rotasi, qty
            for (const item of data_table) {
                // rate * qty * (rotasi jika ada)
                item.amount = flt(item.rate * item.qty * (item.rotasi || 1), precision("amount", item));

                total["amount"] += item.amount;
                total["qty"] += item.qty
                total_rotasi += item.rotasi || 0

                // jika tidak ada fieldname degan kata per_ skip sebaran
                if(per_month_table.length > 0){
                    this.calculate_sebaran_values(item, per_month_table)
                }
            }
            
            total["rotasi"] = total_rotasi / data_table.length;
            
            for (const total_field of ["amount", "qty", "rotasi"]) {
                let fieldname = `${table_name}_${total_field}`
                if (!this.frm.fields_dict[fieldname]) continue;

                this.frm.doc[fieldname] = total[total_field];
            }
        }

        calculate_sebaran_values(item, months=[]){
            // set nilai sebaran
            for (const month of months) {
                let per_month = month.replace(/^rp_/, "per_")
                
                item[month] = flt(
                    item.amount * (this.frm.doc[per_month] / 100),
                    precision(month, item)
                );
            }
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

        add_blok_in_table(blok_table, args, default_field={}){
            let me = this

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
                me.frm.get_field(blok_table).tab.set_active();
            })
        }

        clear_table(list_table=[]){
            for (const field_table of list_table || this.doctype_ref("table_fieldname")) {
                this.frm.clear_table(field_table)
                this.calculate_item_values(field_table)
            }

            this.calculate_grand_total();
            this.frm.refresh_fields();
        }
    }
}