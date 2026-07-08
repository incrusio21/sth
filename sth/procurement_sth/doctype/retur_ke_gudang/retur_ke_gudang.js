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


function link_for(frm) {
	const original_link_formatter = frappe.form.formatters.Link;
	frappe.form.formatters.Link = function (value, docfield, options, doc) {
		if (doc) {
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