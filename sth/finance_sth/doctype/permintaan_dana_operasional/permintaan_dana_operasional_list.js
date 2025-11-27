frappe.listview_settings["Permintaan Dana Operasional"] = {
	primary_action: function () {
		this.new_doctype_dialog();
	},

	new_doctype_dialog() {
		let fields = [
            {
                label: __("Company"),
                fieldname: "company",
                fieldtype: "Link",
                options: "Company",
                reqd: 1,
            },
			{
				label: __("Unit"),
				fieldname: "unit",
				fieldtype: "Link",
                options: "Unit",
				reqd: 1,
			},
            {
				label: __("Months"),
				fieldname: "months",
				fieldtype: "Link",
                options: "Months",
				reqd: 1,
			},
            {
				label: __("Fiscal Year"),
				fieldname: "fiscal_year",
				fieldtype: "Link",
                options: "Fiscal Year",
				reqd: 1,
			},
		];

		let new_d = new frappe.ui.Dialog({
			title: __("Create New Permintaan Dana Operasional"),
			fields: fields,
			primary_action_label: __("Create & Continue"),
			primary_action(values) {
				if (!values.istable) values.editable_grid = 0;
				frappe.db
					.insert({
						doctype: "Permintaan Dana Operasional",
						...values,
						fields: [{ fieldtype: "Section Break" }],
					})
					.then((doc) => {
						frappe.set_route("Form", "Permintaan Dana Operasional", doc.name);
					});
			},
			secondary_action_label: __("Cancel"),
			secondary_action() {
				new_d.hide();
				if (frappe.get_route()[0] === "Form") {
					frappe.set_route("List", "Permintaan Dana Operasional");
				}
			},
		});
		new_d.show();
	},
};
