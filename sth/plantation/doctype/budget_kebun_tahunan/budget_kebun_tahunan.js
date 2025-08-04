// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Budget Kebun Tahunan", {
	refresh(frm) {
        frm.set_query("unit", function(doc){
            if(!doc.company){
                frappe.throw("Please Select Company First")
            }

		    return{
		        filters: {
                    company: doc.company
                }
		    }
		})
	},
    company(){
        frm.set_value("unit", "")
    }
});
