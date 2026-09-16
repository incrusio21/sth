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
									// Hanya Receive "Lain - Lain" yang dibeli lewat PO dan
									// berakhir di Purchase Receipt; TBS punya alurnya sendiri.
									'receive_type': "Lain - Lain",
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
								if (!timbangan.kode_barang) {
									frappe.msgprint(__('Timbangan {0} belum punya Kode Barang.', [timbangan.name]));
									return;
								}

								// Baris kosong bawaan form baru dipakai ulang supaya item
								// pertama tidak jatuh di baris kedua.
								let row = baris_item_kosong(frm) || frm.add_child('items');
								row.item_code = timbangan.kode_barang;

								// Nama barang, UOM, dan gudang diisi handler item_code
								// standar ERPNext, qty baru ditimpa setelah itu selesai.
								frm.script_manager.trigger('item_code', row.doctype, row.name).then(function() {
									frappe.model.set_value(row.doctype, row.name, 'timbangan', timbangan.name);
									frappe.model.set_value(row.doctype, row.name, 'qty',
										flt(timbangan.netto) - flt(timbangan.potongan_sortasi) / 100);

									buang_baris_item_kosong(frm);
									frm.refresh_field('items');

									frappe.msgprint(__('Item added from Timbangan {0}', [timbangan.name]));
								});
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

// Baris yang belum terisi item_code: entah baris kosong bawaan grid saat form
// baru, entah baris yang dibuka user lalu ditinggalkan.
function baris_item_kosong(frm){
	return (frm.doc.items || []).find(row => !row.item_code);
}

function buang_baris_item_kosong(frm){
	let terisi = (frm.doc.items || []).filter(row => row.item_code);
	if (terisi.length == (frm.doc.items || []).length) return;

	frm.doc.items = terisi;
	terisi.forEach((row, i) => row.idx = i + 1);
}
