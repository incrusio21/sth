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
	},
	setup(frm) {
		frm.set_query("divisi", sth.queries.divisi)
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
