frappe.ui.form.on("Item Group", {
	onload: function(frm) {

		if (frm.is_new() && !frm.doc.custom_item_group_code) {
            generate_kode_item_group(frm);
        }
        frm.set_df_property('custom_item_group_code', 'read_only', 1);
	},
});

function generate_kode_item_group(frm) {
    frappe.call({
        method: 'sth.overrides.item_group.get_next_group_code',
        callback: function(r) {
            if (r.message) {
                frm.set_value('custom_item_group_code', r.message);
            }
        }
    });
}