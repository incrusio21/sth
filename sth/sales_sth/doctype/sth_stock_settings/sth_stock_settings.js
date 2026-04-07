frappe.ui.form.on("STH Stock Settings", {
	onload: function(frm) {
		set_akun_query(frm);
	}
});

frappe.ui.form.on('STH Stock Settings Table', {

	form_render: function(frm, cdt, cdn) {
		set_akun_query(frm, cdt, cdn);
	}
});

function set_akun_query(frm, cdt, cdn) {
	frm.fields_dict['sth_stock_settings_table'].grid.get_field('stock_in_transit_account').get_query = function(doc, cdt, cdn) {
		let row = locals[cdt][cdn];
		return {
			filters: {
				company: row.company,
				is_group: 0
			}
		};
	};
}