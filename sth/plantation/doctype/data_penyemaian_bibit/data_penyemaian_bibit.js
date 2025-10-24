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
                    ["per_penyemaian", "<", 100]                    
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
        sth.form.reset_value(frm, ["purchase_receipt_item", "item_code", "batch"])
    },
    select_item(frm){
        const fields = [
            {
                fieldtype: "Data",
                fieldname: "detail_name",
                hidden: 1,
                read_only: 1,
                label: __("New Doc")
            },
            {
                fieldtype: "Link",
                fieldname: "item_code",
                options: "Item",
                in_list_view: 1,
                read_only: 1,
                disabled: 0,
                label: __("Item")
            },
            {
                fieldtype: "Link",
                fieldname: "batch_no",
                options: "Batch",
                in_list_view: 1,
                read_only: 1,
                disabled: 0,
                label: __("Batch")
            },
            {
                fieldtype: "Float",
                fieldname: "remaining_qty",
                in_list_view: 1,
                read_only: 1,
                disabled: 0,
                label: __("Remaining Qty")
            },
        ]

        frappe.call({
            method: "sth.plantation.doctype.data_penyemaian_bibit.data_penyemaian_bibit.select_purchase_receipt_item",
            args: {
                voucher_no: frm.doc.voucher_no
            },
            freeze: true,
            callback: function (data) {
                if (data.message.length == 0) {
                    frappe.throw(__("Item Not Found."))
                }

                const dialog = new frappe.ui.Dialog({
                    title: __("Select Item"),
                    size: "large",
                    fields: [
                        {
                            fieldname: "trans_item",
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
                        const selected_items = dialog.fields_dict.trans_item.grid.get_selected_children();

                        if (selected_items.length != 1) {
                            frappe.throw("Please Select at One Item")
                        }
                        
                        frm.doc.purchase_receipt_item =  selected_items[0].detail_name
                        frm.doc.item_code =  selected_items[0].item_code
                        frm.doc.item_code =  selected_items[0].item_code
                        frm.doc.batch =  selected_items[0].batch_no
                        frm.doc.qty_planting =  selected_items[0].remaining_qty

                        frm.trigger("calculate_qty")
                        
                        dialog.hide();
                    },
                    primary_action_label: __("Select Item"),
                });

                dialog.show();
            }
        })
    },

    qty_planting(frm){
        frm.trigger("calculate_qty")
    },

    qty_before_afkir(frm){
        frm.trigger("calculate_qty")
    },

    calculate_qty(frm){
        frm.doc.qty = flt(frm.doc.qty_planting - frm.doc.qty_before_afkir)

        frm.refresh_fields()
    }
});