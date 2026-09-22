// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt


function set_series(frm) {
	if (frm.doc.transaction_type == "Receive") {
		frm.set_value("naming_series", "REC-.DD.MM.YY.-.###");
	}

	if (frm.doc.transaction_type == "Dispatch") {
		frm.set_value("naming_series", "DIS-.DD.MM.YY.-.###");
	}

	if (frm.doc.transaction_type == "Return") {
		frm.set_value("naming_series", "RET-.DD.MM.YY.-.###");
	}
}

frappe.ui.form.on("Security Check Point", {
	refresh(frm) {
		set_series(frm);

		if (frm.doc.docstatus == 0) {
			frm.add_custom_button(__('Scan QR DO'), function () {
				new frappe.ui.Scanner({
					dialog: true,
					multiple: false,
					on_scan(data) {
						const teks = data && data.result && data.result.text
						if (teks) {
							frm.events.proses_qr_do(frm, teks)
						}
					},
				})
			})
		}
	},

	scan_qr_do(frm) {
		// Scanner kabel mengetik isinya lalu Enter; kolomnya langsung dikosongkan
		// supaya scan berikutnya tetap memicu perubahan nilai.
		const teks = frm.doc.scan_qr_do
		if (!teks) return

		frm.set_value('scan_qr_do', '')
		frm.events.proses_qr_do(frm, teks)
	},

	proses_qr_do(frm, teks) {
		frappe.call({
			method: 'sth.sales_sth.doctype.delivery_order.delivery_order.resolve_qr_transporter',
			args: { qr_text: teks },
		}).then((r) => {
			if (!r.message) return

			const data = r.message

			// Urutannya penting: transaction_type mereset ketiga jenis transaksi dan
			// dispatch_type mengosongkan do_no, jadi DO selalu diisi paling akhir.
			frm.set_value('transaction_type', 'Dispatch')
				.then(() => frm.set_value('dispatch_type', 'Product'))
				.then(() => {
					if (!data.driver) return
					return frm.set_value('qr_code_scan', data.driver)
				})
				.then(() => frm.set_value('do_no', data.delivery_order))
				.then(() => {
					// Baris tanpa Driver terdaftar tetap membawa no polisinya supaya
					// petugas pos tidak mengetik ulang.
					if (data.driver || !data.vehicle_no) return
					return frm.set_value('license_plate', data.vehicle_no)
				})
				.then(() => {
					frm.events.tampilkan_keterangan_do(frm, data)
				})
		})
	},

	tampilkan_keterangan_do(frm, data) {
		// Muatannya cuma keterangan buat petugas pos mencocokkan isi bak; yang
		// dipakai transaksi tetap items_do yang diisi handler do_no.
		const baris = [
			__('DO {0}', [data.delivery_order]),
			data.driver_name || data.vehicle_no || '',
		].filter((teks) => teks)

		const muatan = (data.barang || []).map((row) => {
			return [row.item_name || row.item_code, format_number(row.qty), row.uom || '']
				.filter((bagian) => bagian)
				.join(' ')
		})

		if (muatan.length) {
			baris.push(__('Muatan') + ': ' + muatan.join(', '))
		}

		frappe.show_alert({ message: baris.join('<br>'), indicator: 'green' }, 10)
	},

	setup(frm) {
		// kebun cuma boleh unit kebun milik company dokumen ini — pabrik dan HO
		// tidak pernah jadi pengirim buah
		frm.set_query("kebun", (doc) => {
			return {
				filters: {
					company: doc.company,
					plantation: 1
				}
			}
		})

		// divisi ikut kebun, bukan unit: unit di dokumen ini pabrik tempat posnya
		// berdiri, sedangkan divisi yang dicari milik kebun pengirimnya
		frm.set_query("divisi", (doc) => {
			return {
				filters: {
					unit: doc.kebun
				}
			}
		})

		frm.set_query("unit", (doc) => {
			return {
				filters: {
					company: doc.company
				}
			}
		})

		frm.set_query("ticket_number", (doc) => {
			return {
				filters: {
					exit: false
				}
			}
		})

		frm.set_query("do_no", (doc) => {
			return {
				query: frappe.model.get_server_module_name(doc.doctype) + ".delivery_order_query",
				filters: {
					driver: doc.qr_code_scan
				}
			}
		})
	},

	onload(frm) {
		cur_frm.add_fetch("do_no", "unit", "unit")
		cur_frm.add_fetch("spb", "unit", "unit")

		frm.set_query("spb", function () {
			return {
				filters: {
					company: frm.doc.company
				}
			};
		});
	},

	company(frm) {
		frm.set_query("spb", function () {
			return {
				filters: {
					company: frm.doc.company
				}
			};
		});
	},

	transaction_type(frm) {
		frm.events.clear_fields(frm, "transaction")
		set_series(frm);

	},

	receive_type(frm) {
		frm.events.clear_fields(frm, "receive")
	},

	dispatch_type(frm) {
		frm.events.clear_fields(frm, "dispatch")
	},

	return_type(frm) {
		frm.events.clear_fields(frm, "dispatch")
	},


	clear_fields(frm, type) {
		const field_clear = {
			transaction: ["receive_type", "dispatch_type", "return_type"],
			receive: ["spb", "purchase_order"],
			dispatch: ["do_no", "items_do"]
		}
		field_clear[type].forEach((row) => {
			frm.set_value(row, "")
		})
	},

	exit(frm) {
		if (frm.doc.exit) {
			frappe.call({
				method: 'frappe.client.get_list',
				args: {
					doctype: 'Timbangan',
					filters: {
						'ticket_number': frm.doc.name,
						'docstatus': ['<', 2]
					},
					fields: ['name', 'weight_out_time']
				},
				async: false,
				callback: function (r) {
					if (r.message && r.message.length > 0) {
						if (r.message[0].weight_out_time === '00:00:00') {

							frm.set_value("exit", 0)
							frappe.throw('Timbangan Belum Selesai');
							return
						}
						else {
							const time = frm.doc.exit ? moment().format("HH:mm:ss") : "00:00:00"
							frm.set_value("vehicle_exit_time", time)
						}
					} else {
						// No Timbangan found

						frm.set_value("exit", 0)
						frappe.throw('Timbangan Belum Dibuat');
						return
					}
				}
			});
		}


	},
	do_no: function (frm) {
		if (frm.doc.do_no) {
			frappe.call({
				method: 'frappe.client.get',
				args: {
					doctype: 'Delivery Order',
					name: frm.doc.do_no,
				},
				callback: function (r) {
					if (r.message && r.message.items) {
						let item_code = r.message.items[0].item_code;
						let reference = r.message.items[0].name;
						frm.set_value('items_do', item_code);
						frm.set_value('items_do_reference', reference);
					}
				}
			});
		} else {
			frm.set_value('items_do', '');
		}
	}
});
