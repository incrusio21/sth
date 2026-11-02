// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

// Handler child table disimpan per child doctype, bukan per parent. VAT Detail
// juga dipakai Purchase Invoice, Purchase Order dan Supplier Quotation, jadi
// begitu salah satunya dibuka handlernya ikut jalan di form lain. Kembarannya
// ada di script doctype-doctype itu.
function hanya_untuk_doctype(doctypes, handlers) {
    doctypes = [].concat(doctypes)
    return Object.fromEntries(Object.entries(handlers).map(([event, handler]) => [
        event,
        function (frm, ...args) {
            if (doctypes.includes(frm.doctype)) return handler.call(this, frm, ...args)
        },
    ]))
}

frappe.ui.form.on("VAT Detail", hanya_untuk_doctype(["BAPP", "Proposal"], {
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
}));

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