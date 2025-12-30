// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

sth.plantation.mandor_field = {
    mandor_fields: {},
    get_mandor_fields: async function (doctype){
        await frappe.model.with_doctype(doctype);

        // frm.fields_dict.reference.grid.update_docfield_property("employee_field", "options", options);

        

        return options;
    },
    setup_all_row(frm){
        for(const item of frm.doc.mandor_premi){
            let row = frm.fields_dict.mandor_premi.grid.grid_rows_by_docname[item.name]

            this.setup_fieldname_select(item.voucher_type, row)
        }
    },
    setup_fieldname_select: async function (doctype, row) {
        // get the doctype to update fields
		if (!doctype) return;

        frappe.model.with_doctype(doctype, function () {
            let get_select_options = function (df, parent_field) {
                // Append parent_field name along with fieldname for child table fields
                let select_value = parent_field ? df.fieldname + "," + parent_field : df.fieldname;

                return {
                    value: select_value,
                    label: df.fieldname + " (" + __(df.label, null, df.parent) + ")",
                };
            };

            let fields = frappe.get_doc("DocType", doctype).fields;
            let options = $.map(fields, function (d) {
                return d.fieldtype == "Link" && d.options == "Employee" && !d.read_only
                    ? get_select_options(d)
                    : null;
            });
            
            let docfield = row?.docfields?.find((d) => d.fieldname === "employee_field");
            if (docfield) {
                docfield["options"] = options
            } else {
                throw `field ${fieldname} not found`;
            }
		});
        
    }
}

frappe.ui.form.on("Plantation Settings", {
	refresh(frm) {
        sth.plantation.mandor_field.setup_all_row(frm)
	},
});

frappe.ui.form.on("Plantation Mandor Setting", {
	voucher_type(frm, cdt, cdn) {
        let item = frappe.get_doc(cdt, cdn)
        let row = frm.fields_dict.mandor_premi.grid.grid_rows_by_docname[cdn]

        sth.plantation.mandor_field.setup_fieldname_select(item.voucher_type, row)
	},
});
