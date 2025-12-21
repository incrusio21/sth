frappe.ui.form.on("Customer", {
	onload: function(frm) {

		if (frm.is_new() && !frm.doc.kode_pelanggan) {
            generate_kode_customer(frm);
        }

		if (frm.is_new() && frm.komoditi_editor) {
			frm.komoditi_editor.reset();
		}

		if (!frm.is_new()) {
			if(!frm.komoditi_editor){
				const komoditi_area = $('<div class="komoditi-editor">').appendTo(
					frm.fields_dict.custom_komoditi_html.wrapper
				);

				frm.komoditi_editor = new frappe.KomoditiEditor(
					komoditi_area,
					frm,
					0
				);
			}
			else{
				frm.komoditi_editor.show()
			}
			
		}
	},

	refresh: function(frm) {
		if (!frm.is_new() && frm.komoditi_editor) {
			frm.komoditi_editor.show();
		}
	},

	validate: function(frm) {
		if (frm.komoditi_editor) {
			frm.komoditi_editor.set_komoditi_in_table();
		}
	},
});

function generate_kode_customer(frm) {
    frappe.call({
        method: 'sth.overrides.customer.get_next_customer',
        callback: function(r) {
            if (r.message) {
                frm.set_value('kode_pelanggan', r.message);
            }
        }
    });
}