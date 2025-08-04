frappe.provide("frappe.treeview_settings");

frappe.treeview_settings["Kegiatan"] = {
    breadcrumb: "Plantation",
    title: __("Rencana Kegiatan"),
    get_tree_root: false,
	filters: [
		{
			fieldname: "company",
			fieldtype: "Select",
			options: erpnext.utils.get_tree_options("company"),
			label: __("Company"),
			default: erpnext.utils.get_tree_default("company"),
			onchange: function () {
				var me = frappe.treeview_settings["Kegiatan"].treeview;
				var company = me.page.fields_dict.company.get_value();
				if (!company) {
					frappe.throw(__("Please set a Company"));
				}
				me.opts.root_label = company
				// frappe.call({
				// 	method: "erpnext.accounts.doctype.account.account.get_root_company",
				// 	args: {
				// 		company: company,
				// 	},
				// 	callback: function (r) {
				// 		if (r.message) {
				// 			let root_company = r.message.length ? r.message[0] : "";
				// 			me.page.fields_dict.root_company.set_value(root_company);

				// 			frappe.db.get_value(
				// 				"Company",
				// 				{ name: company },
				// 				"allow_account_creation_against_child_company",
				// 				(r) => {
				// 					frappe.flags.ignore_root_company_validation =
				// 						r.allow_account_creation_against_child_company;
				// 				}
				// 			);
				// 		}
				// 	},
				// });
			},
		},
		{
			fieldname: "kategori_kegiatan",
			fieldtype: "Link",
			options: "Kategori Kegiatan",
			label: __("Kategori Kegiatan"),
		},
	],
	root_label: "Kegiatan",
	get_tree_nodes: "sth.plantation.doctype.kegiatan.kegiatan.get_children",
	fields: [
		{
			fieldtype: "Data",
			fieldname: "nm_kgt",
			label: __("New Nama Kegiatan"),
			reqd: true,
		},
		{
			fieldtype: "Data",
			fieldname: "kd_kgt",
			label: __("Kode Kegiatan"),
		},
		{
			fieldtype: "Check",
			fieldname: "is_group",
			label: __("Is Group"),
			onchange: function () {
				if (!this.value) {
					this.layout.set_value("root_type", "");
				}
			},
		},
		{
			fieldtype: "Link",
			fieldname: "kategori_kegiatan",
			label: __("Kategori Kegiatan"),
			options: "Kategori Kegiatan",
			reqd: true,
		},
		{
			fieldtype: "Link",
			fieldname: "tipe_kegiatan",
			label: __("Tipe Kegiatan"),
			options: "Tipe Kegiatan",
			reqd: true,
		},
		{
			fieldtype: "Link",
			fieldname: "uom",
			label: __("Satuan"),
			options: "Uom",
			reqd: true,
		},
		{
			fieldtype: "Link",
			fieldname: "account",
			label: __("Account"),
			options: "Account",
			reqd: true,
		},
		{
			fieldtype: "Link",
			fieldname: "divisi",
			label: __("Divisi"),
			options: "Divisi",
			reqd: true,
		},
	],
	onload: function (treeview) {
		frappe.treeview_settings["Kegiatan"].treeview = {};
		$.extend(frappe.treeview_settings["Kegiatan"].treeview, treeview);
	},
	toolbar: [
		{
			label: __("Add Child"),
			condition: function (node) {
				return (
					frappe.boot.user.can_create.indexOf("Kegiatan") !== -1 &&
					node.expandable &&
					!node.hide_add
				);
			},
			click: function (node) {
				var me = frappe.views.trees["Kegiatan"];
				
				$.extend(me.args, {
					"kategori_kegiatan": node.data.kategori_kegiatan,
					// "tipe_kegiatan": node.data.tipe_kegiatan,
					// "uom": node.data.uom,
				});
				
				me.new_node();
			},
			btnClass: "hidden-xs",
		},
	],
	extend_toolbar: true,
}