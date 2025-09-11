// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Data Penyemaian Bibit", {
    onload: function(frm) {      
        if (frm.is_new() && !frm.doc.posting_time) {
            let now = frappe.datetime.now_time(); 
            frm.set_value("posting_time", now);
        }
    },
	refresh(frm) {
        frm.set_query("voucher_no", function(doc) {
            return {
                "filters": [
                    ["company",  "=", doc.company],
                    ["docstatus",  "=", 1],                    
                ]
            };            
        });
        
        frm.set_query("item_code", function(doc) {
			return {
				query: "sth.plantation.doctype.data_penyemaian_bibit.data_penyemaian_bibit.get_item_code_preci",
                filters: {
                    parent: doc.voucher_no
                }
			}            
		});

        frm.set_query("batch", function(doc) {
			return {
				query: "sth.plantation.doctype.data_penyemaian_bibit.data_penyemaian_bibit.get_batch_preci",
                filters: {
                    parent: doc.voucher_no,
                    item_code: doc.item_code,
                }
			}            
		});
	},
    voucher_no(frm){
        cur_frm.set_value('item_code', null)
        cur_frm.set_value('batch', null)
    },
    item_code(frm){
        cur_frm.set_value('batch', null)
    },
    batch: async function(frm) {
        let total = await calculate_total_qty(frm);
        frm.set_value("qty_planting", total);        
    },
    qty_planting: async function(frm) {                
        await validate_qty_planting(frm);
    },
    qty_before_afkir(frm){
        calculate_grand_total_qty(frm);
    }
});

async function validate_qty_planting(frm) {
    let total = await calculate_total_qty(frm);
    if(frm.doc.qty_planting>total){
        frm.set_value("qty_planting", total);
        frappe.msgprint("Qty Planting must not be greater than " + total);
    }else if(frm.doc.qty_planting<0){
        frm.set_value("qty_planting", total);
        frappe.msgprint("Qty Planting must not be less than 0");
    }
    calculate_grand_total_qty(frm);
}

async function calculate_total_qty(frm) {
    if (frm.doc.voucher_no && frm.doc.item_code && frm.doc.batch) {
        let r = await frappe.call({
            method: "sth.plantation.doctype.data_penyemaian_bibit.data_penyemaian_bibit.get_total_qty",
            args: {
                parent: frm.doc.voucher_no,
                item_code: frm.doc.item_code,
                batch_no: frm.doc.batch
            }
        });
        return r.message || 0;
    }
    return 0;
}

function calculate_grand_total_qty(frm) {
    frm.set_value("qty", frm.doc.qty_planting-frm.doc.qty_before_afkir);
}