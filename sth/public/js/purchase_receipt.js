frappe.ui.form.on('Purchase Receipt', {
	refresh: function(frm) {
		make_timbangan_button(frm)
	}
});

function make_timbangan_button(frm){
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
									'type': "Receive",
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
								
								// // Set header fields
								// if (timbangan.driver_name) {
								// 	frappe.call({
								// 		method: 'frappe.client.get_value',
								// 		args: {
								// 			doctype: 'Driver',
								// 			filters: { 'full_name': timbangan.driver_name },
								// 			fieldname: 'name'
								// 		},
								// 		callback: function(driver_r) {
								// 			if (driver_r.message) {
								// 				frm.set_value('driver', driver_r.message.name);
								// 				frm.set_value('driver_name', timbangan.driver_name);
								// 			}
								// 		}
								// 	});
								// }
								
								// if (timbangan.transportir) {
								// 	frappe.call({
								// 		method: 'frappe.client.get_value',
								// 		args: {
								// 			doctype: 'Supplier',
								// 			filters: { 
								// 				'supplier_name': timbangan.transportir,
								// 				'is_transporter': 1
								// 			},
								// 			fieldname: 'name'
								// 		},
								// 		callback: function(trans_r) {
								// 			if (trans_r.message) {
								// 				frm.set_value('transporter', trans_r.message.name);
								// 				frm.set_value('transporter_name', timbangan.transportir);
								// 			}
								// 		}
								// 	});
								// }
								
								// if (timbangan.license_number) {
								// 	frm.set_value('lr_no', timbangan.license_number);
								// }
								
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