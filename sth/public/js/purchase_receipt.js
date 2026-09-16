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
								isi_dari_timbangan(frm, timbangan);
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

function isi_dari_timbangan(frm, timbangan){
	if (!timbangan.kode_barang) {
		frappe.msgprint(__('Timbangan {0} belum punya Kode Barang.', [timbangan.name]));
		return;
	}

	ambil_detail_po(timbangan).then((detail) => {
		let supplier = detail.supplier || timbangan.supplier;

		if (supplier && frm.doc.supplier && frm.doc.supplier != supplier) {
			frappe.msgprint(__('Timbangan {0} memasok dari {1}, sedangkan Purchase Receipt ini untuk {2}. Barangnya tidak ditambahkan.',
				[timbangan.name, supplier, frm.doc.supplier]));
			return;
		}

		// Suppliernya dipasang lebih dulu, baru barangnya: harga, price list, dan
		// termin baris item diambil handler item_code menurut supplier yang
		// sedang terpasang di form.
		let siap = (supplier && !frm.doc.supplier)
			? frm.set_value('supplier', supplier)
			: Promise.resolve();

		siap.then(() => tambah_item_timbangan(frm, timbangan, detail));
	});
}

// Supplier Receive "Lain - Lain" tidak datang dari QR supir seperti TBS
// Eksternal; yang mengikat siapa pemasoknya cuma PO-nya. Baris PO-nya ikut
// diambil sekalian, dari PO-nya langsung dan bukan dari field di Timbangan,
// supaya dokumen lama dan yang masuk lewat API — yang fieldnya bisa kosong —
// tetap kebagian.
function ambil_detail_po(timbangan){
	if (!timbangan.purchase_order) {
		return Promise.resolve({});
	}

	return frappe.xcall('sth.mill.doctype.timbangan.timbangan.baris_po_untuk_timbangan',
		{ timbangan: timbangan.name }).then((detail) => detail || {});
}

function tambah_item_timbangan(frm, timbangan, detail){
	// Baris kosong bawaan form baru dipakai ulang supaya item pertama tidak
	// jatuh di baris kedua.
	let row = baris_item_kosong(frm) || frm.add_child('items');
	row.item_code = timbangan.kode_barang;

	// Nama barang, UOM, dan gudang diisi handler item_code standar ERPNext,
	// angka dari PO dan timbangan baru ditimpa setelah itu selesai.
	frm.script_manager.trigger('item_code', row.doctype, row.name).then(function() {
		frappe.model.set_value(row.doctype, row.name, 'timbangan', timbangan.name);

		return samakan_dengan_po(row, detail).then(function() {
			return frappe.model.set_value(row.doctype, row.name, 'qty',
				flt(timbangan.netto) - flt(timbangan.potongan_sortasi) / 100);
		});
	}).then(function() {
		buang_baris_item_kosong(frm);
		frm.refresh_field('items');

		lapor_item_timbangan(timbangan, detail);
	});
}

// UOM harus sama persis dengan baris PO-nya, begitu juga project: ERPNext
// membandingkan keduanya — beserta item_code — waktu Purchase Receipt
// divalidasi terhadap PO, dan menolak dokumennya kalau berbeda. Rate ikut
// disamakan karena Buying Settings bisa menuntut harga yang sama sepanjang
// siklus pembelian.
function samakan_dengan_po(row, detail){
	if (!detail.baris) return Promise.resolve();

	let baris = detail.baris;
	let nilai = {
		purchase_order: detail.purchase_order,
		purchase_order_item: baris.name
	};

	if (baris.warehouse) nilai.warehouse = baris.warehouse;
	if (baris.project) nilai.project = baris.project;

	// Berurutan, bukan sekaligus: handler uom mengisi ulang conversion factor
	// dari tabel konversi item, dan conversion factor menghitung ulang rate.
	// Yang ditulis belakangan yang bertahan.
	return frappe.model.set_value(row.doctype, row.name, nilai)
		.then(() => frappe.model.set_value(row.doctype, row.name, 'uom', baris.uom))
		.then(() => frappe.model.set_value(row.doctype, row.name, 'conversion_factor', baris.conversion_factor))
		.then(() => frappe.model.set_value(row.doctype, row.name, 'rate', baris.rate));
}

function lapor_item_timbangan(timbangan, detail){
	let pesan = [__('Item added from Timbangan {0}', [timbangan.name])]

	if (timbangan.purchase_order && !detail.baris) {
		pesan.push(__('{0} tidak punya baris untuk {1}, jadi barisnya tidak ditautkan ke PO.',
			[timbangan.purchase_order, timbangan.kode_barang]))
	}

	// Netto timbangan selalu kilogram, sementara baris PO boleh memakai UOM
	// lain — PCS, Liter, Ton. Qty-nya tidak dikonversi sendiri karena faktor
	// konversi item belum tentu berlaku untuk berat; yang tahu cuma operatornya.
	if (detail.baris && !uom_kilogram(detail.baris.uom)) {
		pesan.push(__('Qty diisi dari netto timbangan dalam kilogram, sementara baris PO memakai UOM {0}. Periksa qty-nya.',
			[detail.baris.uom]))
	}

	frappe.msgprint(pesan.join('<br>'))
}

function uom_kilogram(uom){
	return /^(kg|kgs|kilogram)$/i.test(String(uom || '').trim())
}
