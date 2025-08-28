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

        rotasi(_, cdt, cdn){
            this.calculate_total(cdt, cdn)
        }

        add_blok_in_table(blok_table, args, default_field={}){
            let me = this

            this.get_blok_list({ args }, (data) => {
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
            for (const field_table of list_table || []) {
                this.frm.clear_table(field_table)
                this.calculate_item_values(field_table)
            }

            this.calculate_grand_total();
            this.frm.refresh_fields();
        }
    }
}