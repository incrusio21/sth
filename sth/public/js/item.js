frappe.ui.form.on('Item', {
	onload: function(frm) {
	
		if(!frm.is_new()){
			if(frm.doc.persetujuan_1){
				frm.set_df_property('persetujuan_1', 'read_only', 1);
			}
			if(frm.doc.persetujuan_2){
				frm.set_df_property('persetujuan_2', 'read_only', 1);
			}
		}
		frm.set_df_property('item_code', 'read_only', 1);

		if(frm.doc.disabled == 1){
			frm.set_value('status', 'Non Aktif');
		}
		else if(frm.doc.disabled == 0){
			frm.set_value('status', 'Aktif');
		}
	},
	refresh: function(frm){
		if(!frm.is_new()){
			if(frm.doc.persetujuan_1){
				frm.set_df_property('persetujuan_1', 'read_only', 1);
			}
			if(frm.doc.persetujuan_2){
				frm.set_df_property('persetujuan_2', 'read_only', 1);
			}
		}
	},
	item_group: function(frm) {
		if (frm.is_new() && frm.doc.item_group) {
			generate_item_code(frm);
		}
	}
});

function generate_item_code(frm) {
	if (!frm.doc.item_group) {
		frappe.msgprint(__('Please select Item Group first'));
		return;
	}
	
	frappe.call({
		method: 'sth.overrides.item.get_next_item_code',
		args: {
			item_group: frm.doc.item_group
		},
		callback: function(r) {
			if (r.message) {
				frm.set_value('item_code', r.message);
			}
		}
	});
}