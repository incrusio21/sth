// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pengeluaran Barang", {
	setup(frm) {
		frm.set_query("no_permintaan_pengeluaran", function (doc) {
			return {
				filters: {
					pt_pemilik_barang: doc.pt_pemilik_barang,
					docstatus: 1,
					outgoing: ["<", 100],
					status: ["!=", "Closed"]
				}
			}
		})


		frm.set_query("gudang", function (doc) {
			return {
				filters: {
					is_group: 0,
					company: doc.pt_pemilik_barang
				}
			}
		})

		frm.set_query("nama_penerima", function (doc) {
			return {
				filters: {
					unit: doc.unit,
				}
			}
		})
	},
	refresh(frm) {
		frm.set_df_property("items", "cannot_add_rows", true)
	},

	no_permintaan_pengeluaran(frm) {
		if (!frm.doc.no_permintaan_pengeluaran) {
			return
		}

		frm.call("set_items").then((res) => {
			frm.doc.items = res.docs[0].items
			// frappe.model.sync(res)
			frm.refresh()
		})
	}
});


frappe.ui.form.on('Pengeluaran Barang Item', {
	kode_barang: function (frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (frm.doc.gudang && row.kode_barang) {
			frappe.call({
				method: 'frappe.client.get_value',
				args: {
					doctype: 'Bin',
					filters: {
						'warehouse': frm.doc.gudang,
						'item_code': row.kode_barang
					},
					fieldname: ['actual_qty']
				},
				callback: function (r) {
					if (r.message) {
						frappe.model.set_value(cdt, cdn, 'jumlah_saat_ini', r.message.actual_qty || 0);
					} else {
						frappe.model.set_value(cdt, cdn, 'jumlah_saat_ini', 0);
					}
				}
			});
		} else if (!frm.doc.gudang) {
			frappe.msgprint(__('Please select Gudang first'));
			frappe.model.set_value(cdt, cdn, 'kode_gudang', '');
		}
	}
});
