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

		// PO di header — field sth, bukan bawaan ERPNext — cuma diisi kalau masih
		// kosong. Satu Purchase Receipt boleh memuat baris dari beberapa PO,
		// sementara fieldnya cuma memuat satu; yang duluan yang dipegang.
		if (detail.purchase_order && !frm.doc.purchase_order) {
			siap = siap.then(() => frm.set_value('purchase_order', detail.purchase_order));
		}

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
	let terpakai = baris_barang_sama(frm, timbangan, detail);

	let janji = terpakai
		? isi_baris_terpakai(frm, terpakai, timbangan, detail)
		: isi_baris_baru(frm, timbangan, detail);

	janji.then(function() {
		buang_baris_item_kosong(frm);
		frm.refresh_field('items');

		lapor_item_timbangan(frm, timbangan, detail, terpakai);
	});
}

// Baris yang sudah memuat barang yang sama — biasanya hasil Get Items From
// Purchase Order, yang membawa PR/SR dan PO Qty-nya sendiri. Barisnya dipakai
// ulang, bukan ditambah lagi: yang dicatat Purchase Receipt itu satu penerimaan,
// dan qty-nya yang benar adalah hasil timbang.
//
// Baris yang sudah menempel ke timbangan lain dilewati. Dua truk untuk satu
// baris PO tetap butuh dua baris, karena satu baris cuma memuat satu Timbangan.
function baris_barang_sama(frm, timbangan, detail){
	let baris_po = detail.baris && detail.baris.name;

	return (frm.doc.items || []).find(row => !row.timbangan && (baris_po
		? row.purchase_order_item == baris_po
		: row.item_code == timbangan.kode_barang));
}

function isi_baris_terpakai(frm, row, timbangan, detail){
	// Barisnya sudah dipetakan dari PO-nya sendiri, jadi item_code tidak dipicu
	// ulang: itu akan menimpa spesifikasi, merk, dan country dengan isi master
	// Item, dan menghapus PR/SR yang dibawa pemetaan. Yang disamakan cuma baris
	// yang belum tertaut ke PO sama sekali.
	let siap = (detail.baris && !row.purchase_order_item)
		? samakan_dengan_po(row, detail)
		: Promise.resolve();

	return siap
		.then(() => frappe.model.set_value(row.doctype, row.name, 'timbangan', timbangan.name))
		.then(() => frappe.model.set_value(row.doctype, row.name, 'qty', qty_timbangan(timbangan)))
		.then(function() {
			// Harga dari PO dibiarkan apa adanya. Yang dipasang cuma kalau
			// barisnya memang lahir tanpa harga — lihat catatan rate di
			// isi_baris_baru.
			if (!detail.baris || flt(row.rate)) return;

			return frappe.after_ajax(() =>
				frappe.model.set_value(row.doctype, row.name, 'rate', detail.baris.rate));
		});
}

function isi_baris_baru(frm, timbangan, detail){
	// Baris kosong bawaan form baru dipakai ulang supaya item pertama tidak
	// jatuh di baris kedua.
	let row = baris_item_kosong(frm) || frm.add_child('items');
	row.item_code = timbangan.kode_barang;

	// Nama barang, UOM, dan gudang diisi handler item_code standar ERPNext,
	// angka dari PO dan timbangan baru ditimpa setelah itu selesai.
	return frm.script_manager.trigger('item_code', row.doctype, row.name).then(function() {
		frappe.model.set_value(row.doctype, row.name, 'timbangan', timbangan.name);

		return samakan_dengan_po(row, detail).then(function() {
			return frappe.model.set_value(row.doctype, row.name, 'qty', qty_timbangan(timbangan));
		}).then(function() {
			if (!detail.baris) return;

			// Rate paling belakang, dan baru sesudah semua panggilan server reda.
			// Handler uom ERPNext memanggil apply_price_list di callback-nya, dan
			// jawaban panggilan itu menulis ulang rate dari price list — 0 untuk
			// barang yang tidak punya Item Price, dan barang PO seperti pupuk
			// atau solar memang jarang punya. Panggilannya tidak ikut promise
			// set_value, jadi rate yang dipasang lebih awal hilang belakangan
			// tanpa jejak; itu yang bikin baris ini lahir dengan rate 0.
			return frappe.after_ajax(() =>
				frappe.model.set_value(row.doctype, row.name, 'rate', detail.baris.rate));
		});
	});
}

function qty_timbangan(timbangan){
	return flt(timbangan.netto) - flt(timbangan.potongan_sortasi) / 100;
}

// UOM harus sama persis dengan baris PO-nya, begitu juga project: ERPNext
// membandingkan keduanya — beserta item_code — waktu Purchase Receipt
// divalidasi terhadap PO, dan menolak dokumennya kalau berbeda.
//
// Spesifikasi, merk, dan country diambil dari PO, bukan dari default Item:
// itulah yang disepakati dengan supplier, dan handler item_code baru saja
// menimpanya dengan isi master Item.
function samakan_dengan_po(row, detail){
	if (!detail.baris) return Promise.resolve();

	let baris = detail.baris;
	let nilai = {
		purchase_order: detail.purchase_order,
		purchase_order_item: baris.name,
		po_qty: baris.qty
	};

	if (baris.warehouse) nilai.warehouse = baris.warehouse;
	if (baris.project) nilai.project = baris.project;
	if (baris.description) nilai.description = baris.description;
	if (baris.custom_merk) nilai.custom_merk = baris.custom_merk;
	if (baris.custom_country) nilai.custom_country = baris.custom_country;

	// Berurutan, bukan sekaligus: handler uom mengisi ulang conversion factor
	// dari tabel konversi item. Yang ditulis belakangan yang bertahan.
	return frappe.model.set_value(row.doctype, row.name, nilai)
		.then(() => frappe.model.set_value(row.doctype, row.name, 'uom', baris.uom))
		.then(() => frappe.model.set_value(row.doctype, row.name, 'conversion_factor', baris.conversion_factor));
}

function lapor_item_timbangan(frm, timbangan, detail, terpakai){
	let pesan = [terpakai
		? __('Baris {0} dipakai ulang untuk Timbangan {1}, qty-nya diisi dari hasil timbang.',
			[terpakai.idx, timbangan.name])
		: __('Item added from Timbangan {0}', [timbangan.name])]

	if (timbangan.purchase_order && !detail.baris) {
		pesan.push(__('{0} tidak punya baris untuk {1}, jadi barisnya tidak ditautkan ke PO.',
			[timbangan.purchase_order, timbangan.kode_barang]))
	}

	if (detail.purchase_order && frm.doc.purchase_order && frm.doc.purchase_order != detail.purchase_order) {
		pesan.push(__('PO di header tetap {0}; barisnya sendiri menunjuk {1}.',
			[frm.doc.purchase_order, detail.purchase_order]))
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
