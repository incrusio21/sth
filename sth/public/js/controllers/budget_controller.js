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
                    me.calculate_total_sebaran()
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
        
        is_distibute(doc){
            if(doc.is_distibute){

                for (const month of sth.plantation.month) {
                    this.frm.doc[`per_${month}`] = 100 / 12
                }
                
                this.calculate_total_sebaran()
            }
        }
        
        calculate_total_sebaran(){
            let me = this
            let total_sebaran = 0.0
            
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

            
            // set nilai sebaran
            for (const month of sth.plantation.month) {
                total_sebaran += flt(this.frm.doc[`per_${month}`] || 0)
            }

            this.frm.doc.total_sebaran = total_sebaran
            
            me.frm.refresh_fields();
        }

        update_value_after_amount(item){
           item.amount = flt(item.amount * (item.rotasi || 1), precision("amount", item));
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

        after_calculate_item_values(table_name, total){
            // update nilai sebaran dan rotasi jika ada
            let data_table = this.frm.doc[table_name] || []

            // set on child class if 
            let per_month_table = Object.keys(
                this.frm.fields_dict[table_name].grid.fields_map
            ).filter(key => key.includes("rp_"));

            for (const item of data_table) {
                // jika tidak ada fieldname degan kata per_ skip sebaran    
                if(per_month_table.length == 0) continue
                this.calculate_sebaran_values(item, per_month_table)
            }
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