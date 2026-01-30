// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("PPH Detail", {
    type(frm, cdt, cdn){
        let item = locals[cdt][cdn]
        frappe.call({
			method: "sth.utils.data.tax_rate",
			args: {
				tax_name: item.type,
				company: frm.doc.company,
				type: "PPh",
			},
			callback: function(r){
				if(r.message){
					item.percentage = r.message.rate
					item.account = r.message.account
					item.amount = flt(frm.doc.net_total * (item.percentage / 100));
				}
				
                recreate_tax_table(frm)
			}
		})
    }
});

function recreate_tax_table(frm){
		frm.clear_table("taxes")

		let tax_list = []
		if(frm.doc.ppn){
			tax_list.push({
				"account": frm.doc.ppn_account,
                "add_deduct": "Add",
				"amount": frm.doc.ppn_amount
			})
		}

		for (const pph of frm.doc.pph_details) {
			tax_list.push({
				"account": pph.account,
				"add_deduct": "Deduct",
				"amount": pph.amount
			})
		}

		for (const tax of tax_list) {
			tax_value = frm.add_child("taxes");
			tax_value.tipe_pajak = tax.tax_type
			tax_value.charge_type = "Actual";
			tax_value.add_deduct_tax = tax.add_deduct //Deduct
			tax_value.account_head = tax.account;
			tax_value.tax_amount = tax.amount;
		}

		frm.cscript.calculate_taxes_and_totals();
		frm.refresh_fields();
	}