frappe.treeview_settings["Contract Template"] = {
	// Nama dokumen diambil dari title (autoname field:title), jadi dialog Add Child wajib menanyakannya
	fields: [
		{
			fieldtype: "Data",
			fieldname: "title",
			label: __("Title"),
			reqd: 1,
		},
		{
			fieldtype: "Check",
			fieldname: "is_group",
			label: __("Group Node"),
			description: __("Further nodes can be only created under 'Group' type nodes"),
		},
	],
	ignore_fields: ["parent_contract_template"],
};
