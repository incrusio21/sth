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

		const original_link_formatter = frappe.form.formatters.Link;

		frappe.form.formatters.Link = function (value, docfield, options, doc) {
			// Tampilkan plain text untuk Procurement Settings
			if (doc) {
				return value || "";
			}
			// Doctype lain tetap pakai formatter asli
			return original_link_formatter(value, docfield, options, doc);
		};

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

