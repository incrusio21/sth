// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Procurement Settings", {
	onload: function(frm) {
		set_akun_query(frm);
	}
});

frappe.ui.form.on('Akun Pengeluaran Table', {

	form_render: function(frm, cdt, cdn) {
		set_akun_query(frm, cdt, cdn);
	}
});

function set_akun_query(frm, cdt, cdn) {
	frm.fields_dict['akun_pengeluaran_table'].grid.get_field('akun_pengeluaran').get_query = function(doc, cdt, cdn) {
		let row = locals[cdt][cdn];
		return {
			filters: {
				company: row.company,
				is_group: 0
			}
		};
	};
}