// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Procurement Settings", {
	onload: function (frm) {
		frm.set_query("account", "default_account", function (doc, cdt, cdn) {
			let row = locals[cdt][cdn];

			return {
				filters: {
					company: row.company,
					is_group: 0
				}
			};
		});

		pasang_formatter_link_polos();

		set_akun_query(frm);
	},
	refresh: function (frm) {
		frm.fields_dict['item_overreceipt_procurement_settings'].grid.wrapper.on(
			'change',
			function () {
				fix_kode_barang(frm);
			}
		);
		fix_kode_barang(frm);
		set_akun_query(frm);
	}
});

frappe.ui.form.on('Akun Pengeluaran Table', {

	form_render: function (frm, cdt, cdn) {
		set_akun_query(frm, cdt, cdn);
	}
});

// Link di Procurement Settings ditampilkan apa adanya, bukan judul dokumennya:
// yang dipilih di sini kode barang dan nomor akun, dan itu yang mau dilihat.
//
// frappe.form.formatters.Link itu global — satu untuk seluruh desk. Pembungkus
// ini dulu cuma memeriksa `if (doc)`, padahal doc terisi untuk hampir semua link
// yang digambar di dalam form atau grid mana pun. Akibatnya begitu Procurement
// Settings sekali dibuka, link di doctype lain ikut jadi teks biasa yang tidak
// bisa diklik sampai halamannya dimuat ulang. Sekarang cakupannya dilihat dari
// dokumen yang sedang digambar, bukan dari ada-tidaknya dokumen.
let formatter_link_terpasang = false;

function pasang_formatter_link_polos() {
	// onload jalan tiap kali halamannya dibuka; tanpa penjaga ini pembungkusnya
	// menumpuk di atas pembungkus sebelumnya sepanjang sesi.
	if (formatter_link_terpasang) {
		return;
	}

	formatter_link_terpasang = true;

	const formatter_asli = frappe.form.formatters.Link;

	frappe.form.formatters.Link = function (value, docfield, options, doc) {
		if (milik_procurement_settings(doc)) {
			return value || "";
		}

		return formatter_asli(value, docfield, options, doc);
	};
}

function milik_procurement_settings(doc) {
	if (!doc) {
		return false;
	}

	// Baris tabel anak membawa doctype anaknya sendiri, jadi induknya dikenali
	// lewat parenttype.
	return doc.doctype === "Procurement Settings" || doc.parenttype === "Procurement Settings";
}

function fix_kode_barang(frm) {
	let grid = frm.fields_dict['item_overreceipt_procurement_settings'].grid;
	grid.data.forEach((row, i) => {
		let grid_row = grid.grid_rows[i];
		if (!grid_row) return;
		let field = grid_row.columns['item'];
		if (field && field.$value) {
			field.$value.text(row.item); // tampilkan kode asli
		}
	});
}

function set_akun_query(frm, cdt, cdn) {
	frm.fields_dict['akun_pengeluaran_table'].grid.get_field('akun_pengeluaran').get_query = function (doc, cdt, cdn) {
		let row = locals[cdt][cdn];
		return {
			filters: {
				company: row.company,
				is_group: 0
			}
		};
	};


	frm.set_query("account", "ap_in_transit_po_barang", function (doc, cdt, cdn) {
		let row = locals[cdt][cdn];

		return {
			filters: {
				company: row.company,
				is_group: 0
			}
		};
	});
	frm.set_query("account", "ap_in_transit_po_jasa", function (doc, cdt, cdn) {
		let row = locals[cdt][cdn];

		return {
			filters: {
				company: row.company,
				is_group: 0
			}
		};
	});
	frm.set_query("account", "ap_in_transit_proposal", function (doc, cdt, cdn) {
		let row = locals[cdt][cdn];

		return {
			filters: {
				company: row.company,
				is_group: 0
			}
		};
	});
	frm.set_query("account", "hutang_invoice_po_barang", function (doc, cdt, cdn) {
		let row = locals[cdt][cdn];

		return {
			filters: {
				company: row.company,
				is_group: 0
			}
		};
	});
	frm.set_query("account", "hutang_invoice_po_jasa", function (doc, cdt, cdn) {
		let row = locals[cdt][cdn];

		return {
			filters: {
				company: row.company,
				is_group: 0
			}
		};
	});
	frm.set_query("account", "hutang_invoice_proposal", function (doc, cdt, cdn) {
		let row = locals[cdt][cdn];

		return {
			filters: {
				company: row.company,
				is_group: 0
			}
		};
	});
	frm.set_query("account", "uang_muka_po_barang", function (doc, cdt, cdn) {
		let row = locals[cdt][cdn];

		return {
			filters: {
				company: row.company,
				is_group: 0
			}
		};
	});
	frm.set_query("account", "uang_muka_po_jasa", function (doc, cdt, cdn) {
		let row = locals[cdt][cdn];

		return {
			filters: {
				company: row.company,
				is_group: 0
			}
		};
	});
	frm.set_query("account", "uang_muka_proposal", function (doc, cdt, cdn) {
		let row = locals[cdt][cdn];

		return {
			filters: {
				company: row.company,
				is_group: 0
			}
		};
	});
	frm.set_query("account", "persediaan_dalam_perjalanan_procurement_settings", function (doc, cdt, cdn) {
		let row = locals[cdt][cdn];

		return {
			filters: {
				company: row.company,
				is_group: 0
			}
		};
	});
	// frm.set_query("account", "sub_unit_traksi_procurement_settings", function (doc, cdt, cdn) {
	// 	let row = locals[cdt][cdn];

	// 	return {
	// 		filters: {
	// 			company: row.company,
	// 			is_group: 0,
	// 			root_type: "Expense"
	// 		}
	// 	};
	// });
	frm.set_query("account", "procurement_settings_pengakuan_pembelian_tbs_account", function (doc, cdt, cdn) {
		let row = locals[cdt][cdn];

		return {
			filters: {
				company: row.company,
				is_group: 0
			}
		};
	});
}

