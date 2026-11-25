// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Retur Ke Gudang", {
	onload(frm){
		link_for(frm)
	},
	setup(frm) {
		frm.set_query("no_pengeluaran", function (doc) {
			return {
				filters: {
					return_percentage: ["<", "100"],
					pt_pemilik_barang: doc.pemilik,
					docstatus: 1
				}
			}
		})
	},

	// calculate_retur(frm) {
	//     let jumlah = 0

	//     frm.doc.items.forEach((row) => {
	//         jumlah += row.jumlah
	//     })
	//     frm.set_value("jumlah_retur", jumlah)
	// },

	no_pengeluaran(frm) {
		if (!frm.doc.no_pengeluaran) {
			return
		}

		frm.call("set_items").then((res) => {
			frappe.model.sync(res)
			// frm.trigger('calculate_retur')
			frm.refresh()
		})
	}
});

frappe.ui.form.on("Retur Items", {
	jumlah(frm, cdt, cdn) {
		frm.trigger('calculate_retur')
	}
})


// frappe.form.formatters.Link itu global untuk seluruh desk. Dulu pembungkus ini
// cuma memeriksa `if (doc)`, padahal doc terisi untuk hampir semua link yang
// digambar di form, grid maupun Report Builder doctype lain, sehingga Link Title
// di sana ikut hilang sampai halaman dimuat ulang. Sekarang hanya berlaku untuk
// dokumen Retur ke Gudang dan baris tabel anaknya, dan cuma dipasang sekali per sesi.
let formatter_link_retur_terpasang = false;

function link_for(frm) {
	if (formatter_link_retur_terpasang) return;
	formatter_link_retur_terpasang = true;

	const original_link_formatter = frappe.form.formatters.Link;
	frappe.form.formatters.Link = function (value, docfield, options, doc) {
		if (doc && (doc.doctype === "Retur ke Gudang" || doc.parenttype === "Retur ke Gudang")) {
			if (!value) return "";

			// doctype tujuan diambil dari options field Link
			const doctype = docfield.options;
			if (!doctype) return value;

			// bangun route ke form doctype tsb
			const route = frappe.utils.get_form_link(doctype, value);

			return `<a href="${route}">${frappe.utils.escape_html(value)}</a>`;
		}
		// Doctype lain tetap pakai formatter asli
		return original_link_formatter(value, docfield, options, doc);
	};
}