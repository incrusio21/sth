frappe.ui.form.on('Supplier', {
	setup: function (frm) {
		frm.set_query("user_email", "struktur_supplier", (doc) => {
			return {
				filters: {
					supplier: doc.name
				}
			}
		})
	},
	onload: function (frm) {
		if (frm.is_new() && !frm.doc.kode_supplier) {
			generate_kode_supplier(frm);
		}
		hide_details(frm)
		load_kriteria_dokumen_finance(frm)

	},
	refresh: function (frm) {
		if (frm.is_new()) {
			frm.set_value('aktif', 1); // Set checkbox checked by default
			frm.set_value('default', 'Ya');
			frm.set_value('status_bank', 'Aktif');
		}
		check_status_pkp(frm)
		hide_details(frm)
	},
	aktif: function (frm) {
		if (frm.doc.aktif) {
			frm.set_value('default', 'Ya');
			frm.set_value('status_bank', 'Aktif');
		} else {
			frm.set_value('default', 'Tidak');
			frm.set_value('status_bank', 'Tidak Aktif');
		}
	},
	status_pkp: function (frm) {
		check_status_pkp(frm)
	},
});

function generate_kode_supplier(frm) {
	frappe.call({
		method: 'sth.overrides.supplier.get_next_supplier',
		callback: function (r) {
			if (r.message) {
				frm.set_value('kode_supplier', r.message);
			}
		}
	});
}

function check_status_pkp(frm) {
	if (frm.doc.status_pkp) {
		frm.set_df_property('no_sppkp', 'read_only', 0);
	} else {
		frm.set_df_property('no_sppkp', 'read_only', 1);
	}
}

function hide_details(frm) {
	frm.set_df_property('section_break_vmze3', 'hidden', 1);
	frm.set_df_property('section_break_d3qta', 'hidden', 1);
	frm.set_df_property('section_break_1lvsu', 'hidden', 1);
	frm.set_df_property('section_break_vrfr5', 'hidden', 1);
	frm.set_df_property('pajak_label', 'hidden', 1);
	frm.set_df_property('section_break_6doas', 'hidden', 1);

}

function load_kriteria_dokumen_finance(frm) {
	if (frm.is_new()) {
		frappe.call({
			method: 'frappe.client.get',
			args: {
				doctype: 'Kriteria Dokumen Finance',
				name: 'Supplier'
			},
			callback: function (r) {
				if (r.message) {
					let kriteria_doc = r.message;
					// Clear existing rows in the target table (if any)
					frm.clear_table('kriteria_upload_dokumen_finance');
					if (kriteria_doc.kriteria_dokumen_finance && kriteria_doc.kriteria_dokumen_finance.length > 0) {

						kriteria_doc.kriteria_dokumen_finance.forEach(function (row) {
							if (row["rincian_dokumen_finance"] != "SPPKP") {
								let new_row = frm.add_child('kriteria_upload_dokumen_finance');

								Object.keys(row).forEach(function (key) {
									if (['rincian_dokumen_finance'].includes(key)) {
										new_row["rincian_dokumen_finance"] = row["rincian_dokumen_finance"];
									}
								});
							}
						});

						frm.refresh_field('kriteria_upload_dokumen_finance');

					} else {

					}
				} else {
				}
			}
		});
	}
}

frappe.ui.form.on('Struktur Supplier', {
	add_jenis_usaha: function (frm, cdt, cdn) {
		let row = locals[cdt][cdn];

		let d = new frappe.ui.Dialog({
			title: __('Select Item Groups'),
			fields: [
				{
					fieldname: 'item_groups',
					fieldtype: 'MultiSelectList',
					label: __('Item Groups'),
					options: [],
					get_data: function () {
						return frappe.call({
							method: 'frappe.client.get_list',
							args: {
								doctype: 'Item Group',
								filters: {
									is_group: 1
								},
								fields: ['item_group_name', 'name'],
								order_by: 'name asc',
								limit_page_length: 0
							}
						}).then(r => {
							return r.message.map(item => ({
								value: item.item_group_name,
								description: item.name
							}));
						});
					}
				}
			],
			primary_action_label: __('Select'),
			primary_action: function (values) {
				if (values.item_groups && values.item_groups.length > 0) {
					let selected_groups = values.item_groups.join(', ');

					frappe.model.set_value(cdt, cdn, 'jenis_usaha', selected_groups);

					frm.refresh_field('struktur_supplier');
				}
				d.hide();
			}
		});

		if (row.jenis_usaha) {
			let existing_values = row.jenis_usaha.split(',').map(v => v.trim());
			d.fields_dict.item_groups.df.default = existing_values;
		}

		d.show();
	}
});