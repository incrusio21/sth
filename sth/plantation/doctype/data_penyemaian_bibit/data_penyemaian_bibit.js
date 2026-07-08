// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Data Penyemaian Bibit", {
    setup(frm) {
        frm.set_query("voucher_no", function(doc) {
            return {
                query: "sth.api.get_pengeluaran_barang_bibit",
                filters: {
                    company: doc.company
                }
            };
        });
    },
    onload: function(frm) {      
        if (frm.is_new() && !frm.doc.posting_time) {
            let now = frappe.datetime.now_time(); 
            frm.set_value("posting_time", now);
        }
    },
	refresh(frm) {
        // frm.set_query("voucher_no", function(doc) {
        //     return {
        //         "filters": [
        //             ["pt_pemilik_barang",  "=", doc.company],
        //             ["docstatus",  "=", 1]                 
        //         ]
        //     };            
        // });
        
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
        if(frm.doc.docstatus == 1){
            show_gl_button(frm)
        }
        if(frm.is_new()){
            isi_account_company(frm)
        }

	},
    company: function(frm) {
        isi_account_company(frm)
    },
    voucher_no(frm){
        sth.form.reset_value(frm, ["pengeluaran_barang_item", "item_code", "batch"])
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
                fieldtype: "Data",
                fieldname: "kode_barang",
                in_list_view: 1,
                read_only: 1,
                disabled: 0,
                label: __("Item")
            },
            {
                fieldtype: "Data",
                fieldname: "item_name",
                in_list_view: 1,
                read_only: 1,
                disabled: 0,
                label: __("Nama Item")
            },
            {
                fieldtype: "Float",
                fieldname: "jumlah",
                in_list_view: 1,
                read_only: 1,
                disabled: 0,
                label: __("Remaining Qty")
            },
        ]

        frappe.call({
            method: "sth.plantation.doctype.data_penyemaian_bibit.data_penyemaian_bibit.select_pengeluaran_barang_item",
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

                        console.log(selected_items[0])
                        
                        frm.doc.pengeluaran_barang_item =  selected_items[0].detail_name
                        frm.doc.item_code = selected_items[0].kode_barang
                        frm.doc.qty_planting =  selected_items[0].jumlah

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

    calculate_qty(frm){
        frm.doc.qty = flt(frm.doc.qty_planting)

        frm.refresh_fields()
    }
});


function show_gl_button(frm){
    if(frm.doc.docstatus == 1){
        frm.add_custom_button(__('GL Entry'), () => {
            frappe.route_options = {
                voucher_no: frm.doc.name,
                voucher_type: frm.doc.doctype,
                from_date: frm.doc.posting_date,
                to_date: frm.doc.posting_date,
                company: frm.doc.company
            };
            frappe.set_route('query-report', 'General Ledger');
        }, __('View'));
    }
}

function isi_account_company(frm){
    if (!frm.doc.company) return;
    frappe.call({
        method: 'sth.plantation.doctype.data_penyemaian_bibit.data_penyemaian_bibit.get_akun_penyemaian',
        args: { company: frm.doc.company },
        callback: (r) => {
            if (r.message) {
                if(!frm.doc.debit_account){
                    frm.set_value('debit_account', r.message.debit_account);
                }
                if(!frm.doc.credit_account){
                    frm.set_value('credit_account', r.message.credit_account);
                }
            }
        }
    });
}
