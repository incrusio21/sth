frappe.ui.form.on('Delivery Note', {
	customer: function(frm) {
		set_komoditi_filter(frm);

		if (frm.doc.komoditi) {
			frm.set_value('komoditi', '');
			frm.clear_table('keterangan_per_komoditi');
			frm.refresh_field('keterangan_per_komoditi');
		}
	},
	
	refresh: function(frm) {
		set_komoditi_filter(frm);
		$.each(frm.fields_dict, function(fieldname, field) {
			if (field.df.fieldtype === 'Currency' && field.df.fieldname != "ongkos_angkut" && field.df.fieldname != "ongkos_angkut_bongkar") {
				frm.set_df_property(fieldname, 'hidden', 1);
			}
		});
		set_query_unit(frm)
		make_timbangan_button(frm)
	},

	komoditi: function(frm) {
		if (frm.doc.komoditi && frm.doc.customer) {
			validate_komoditi(frm);
		}

		if (frm.doc.komoditi) {
			frm.clear_table('keterangan_per_komoditi');
			
			frappe.call({
				method: 'frappe.client.get',
				args: {
					doctype: 'Komoditi',
					name: frm.doc.komoditi
				},
				callback: function(r) {
					if (r.message && r.message.keterangan_per_komoditi) {
						r.message.keterangan_per_komoditi.forEach(function(row) {
							let child_row = frm.add_child('keterangan_per_komoditi');
							child_row.keterangan = row.keterangan;
							child_row.parameter = row.parameter;
						});
						
						frm.refresh_field('keterangan_per_komoditi');
					}
				}
			});
		}
	},
	onload: function(frm){
		set_query_unit(frm)
	},
	company: function(frm){
		set_query_unit(frm)
	}
});

function set_komoditi_filter(frm) {
	if (frm.doc.customer) {
		frappe.call({
			method: 'frappe.client.get',
			args: {
				doctype: 'Customer',
				name: frm.doc.customer
			},
			callback: function(r) {
				if (r.message && r.message.custom_customer_komoditi) {
					let komoditi_list = r.message.custom_customer_komoditi.map(function(row) {
						return row.komoditi;
					});
				
					if (komoditi_list.length > 0) {
						frm.set_query('komoditi', function() {
							return {
								filters: {
									'name': ['in', komoditi_list]
								}
							};
						});
					} else {
						frm.set_query('komoditi', function() {
							return {
								filters: {
									'name': ['in', []]
								}
							};
						});
					}
				}
			}
		});
	} else {
		frm.set_query('komoditi', function() {
			return {};
		});
	}
}

function validate_komoditi(frm) {

	if (!frm.doc.customer) {
		return;
	}
	
	frappe.call({
		method: 'frappe.client.get',
		args: {
			doctype: 'Customer',
			name: frm.doc.customer
		},
		callback: function(r) {
			if (r.message && r.message.custom_customer_komoditi) {
				let komoditi_list = r.message.custom_customer_komoditi.map(function(row) {
					return row.komoditi;
				});
				
				if (!komoditi_list.includes(frm.doc.komoditi)) {
					frappe.msgprint({
						title: __('Invalid Komoditi'),
						indicator: 'red',
						message: __('The selected Komoditi "{0}" is not linked to Customer "{1}". Please select a valid Komoditi.', [frm.doc.komoditi, frm.doc.customer])
					});
					frm.set_value('komoditi', '');
				}
			}
		}
	});
}

function set_query_unit(frm){
	frm.set_query('unit', function() {
		return {
			filters: {
				'company': frm.doc.company
			}
		};
	});
}

function make_timbangan_button(frm) {
	// Add button untuk get dari Timbangan
	if (frm.doc.docstatus == 0) { // Hanya untuk draft
		frm.add_custom_button(__('Timbangan'), function() {
			// Dialog untuk pilih Timbangan
			let d = new frappe.ui.Dialog({
				title: __('Select Timbangan'),
				fields: [
					{
						label: __('Timbangan'),
						fieldname: 'timbangan',
						fieldtype: 'Link',
						options: 'Timbangan',
						reqd: 1,
						get_query: function() {
							return {
								filters: {
									'company': frm.doc.company,
									'type': "Dispatch",
									'docstatus': 1
								}
							};
						}
					}
				],
				primary_action_label: __('Get Items'),
				primary_action(values) {
					frappe.call({
						method: 'frappe.client.get',
						args: {
							doctype: 'Timbangan',
							name: values.timbangan
						},
						callback: function(r) {
							if (r.message) {
								let timbangan = r.message;
								
								// Set header fields
								if (timbangan.driver_name) {
									frappe.call({
										method: 'frappe.client.get_value',
										args: {
											doctype: 'Driver',
											filters: { 'full_name': timbangan.driver_name },
											fieldname: 'name'
										},
										callback: function(driver_r) {
											if (driver_r.message) {
												frm.set_value('driver', driver_r.message.name);
												frm.set_value('driver_name', timbangan.driver_name);
											}
										}
									});
								}
								
								if (timbangan.transportir) {
									frappe.call({
										method: 'frappe.client.get_value',
										args: {
											doctype: 'Supplier',
											filters: { 
												'supplier_name': timbangan.transportir,
												'is_transporter': 1
											},
											fieldname: 'name'
										},
										callback: function(trans_r) {
											if (trans_r.message) {
												frm.set_value('transporter', trans_r.message.name);
												frm.set_value('transporter_name', timbangan.transportir);
											}
										}
									});
								}
								
								if (timbangan.license_number) {
									frm.set_value('lr_no', timbangan.license_number);
								}
								
								// Add item
								if (timbangan.kode_barang && timbangan.netto) {
									let row = frm.add_child('items');
									row.item_code = timbangan.kode_barang;
									row.qty = timbangan.netto - (timbangan.potongan_sortasi / 100);
									row.timbangan = timbangan.name;
									
									frm.refresh_field('items');
									
									frappe.msgprint(__('Item added from Timbangan {0}', [timbangan.name]));
								}
							}
						}
					});
					d.hide();
				}
			});
			d.show();
		}, __('Get Items From'));
	}
}