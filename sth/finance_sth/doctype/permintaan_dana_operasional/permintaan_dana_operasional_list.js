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
				default: frappe.user_defaults.company
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
			async primary_action(values) {
				if (!values.istable) values.editable_grid = 0;
				const res = await frappe.db.get_value("Company", values.company, "*")
				Object.assign(values, {
					"bahan_bakar_debit_to": res.message.default_pdo_bahan_bakar_account,
					"bahan_bakar_credit_to": res.message.default_pdo_credit_account,
					"perjalanan_dinas_credit_to": res.message.default_pdo_credit_account,
					"kas_credit_to": res.message.default_pdo_credit_account,
					"dana_cadangan_credit_to": res.message.default_pdo_credit_account,
					"non_pdo_credit_to": res.message.default_pdo_credit_account,
					"posting_date": frappe.datetime.get_today(),
					"required_by": frappe.datetime.get_today()
				})
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
