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
	},
	aktif: function(frm) {
		if (frm.doc.aktif) {
			frm.set_value('default', 'Ya');
			frm.set_value('status_bank', 'Aktif');
		} else {
			frm.set_value('default', 'Tidak');
			frm.set_value('status_bank', 'Tidak Aktif');
		}
	}
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