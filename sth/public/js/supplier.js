frappe.ui.form.on('Supplier', {
	onload: function(frm) {
		if (frm.is_new() && !frm.doc.kode_supplier) {
			generate_kode_supplier(frm);
		}
	},
	refresh: function(frm) {
		if (frm.is_new()) {
			frm.set_value('aktif', 1); // Set checkbox checked by default
			frm.set_value('default', 'Ya');
			frm.set_value('status_bank', 'Aktif');
		}
		check_status_pkp(frm)
	},
	aktif: function(frm) {
		if (frm.doc.aktif) {
			frm.set_value('default', 'Ya');
			frm.set_value('status_bank', 'Aktif');
		} else {
			frm.set_value('default', 'Tidak');
			frm.set_value('status_bank', 'Tidak Aktif');
		}
	},
	status_pkp: function(frm) {
		check_status_pkp(frm)
	},
});

function generate_kode_supplier(frm) {
	frappe.call({
		method: 'sth.overrides.supplier.get_next_supplier',
		callback: function(r) {
			if (r.message) {
				frm.set_value('kode_supplier', r.message);
			}
		}
	});
}

function check_status_pkp(frm){
	if (frm.doc.status_pkp) {
		frm.set_df_property('no_sppkp', 'read_only', 0);
	} else {
		frm.set_df_property('no_sppkp', 'read_only', 1);
	}
}