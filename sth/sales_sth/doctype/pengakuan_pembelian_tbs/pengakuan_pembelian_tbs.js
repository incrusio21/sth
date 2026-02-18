frappe.ui.form.on('Pengakuan Pembelian TBS', {
	setup(frm) {
		frm.set_query("unit", (doc) => {
			return {
				filters: {
					company: doc.company
				}
			}
		})
	},
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Download PDF"), function () {
				const url =
					"/printview"
					+ "?doctype=" + encodeURIComponent(frm.doc.doctype)
					+ "&name=" + encodeURIComponent(frm.doc.name)
					+ "&format=" + encodeURIComponent("PF Pengakuan Pembelian TBS")
					+ "&trigger_print=1"
					+ "&no_letterhead=1";

				window.open(url, "_blank");
			});
		}
	},
	get_data: function (frm) {
		if (!frm.doc.nama_supplier) {
			frappe.msgprint(__('Please select a supplier first'));
			return;
		}

		frm.call("get_timbangan")
			.then((res) => {
				frappe.model.sync(res);
				frm.refresh();
				frm.dirty()
			})
	},

	jarak(frm) {
		const jarak = frm.doc.jarak
		if (jarak) {
			const method = frappe.model.get_server_module_name(frm.doctype) + "." + "get_rate"
			frappe
				.xcall(method, { jarak })
				.then((res) => {
					frm.set_value("harga", res + frm.doc.subsidi_angkut)
				})
		}
	},

	subsidi_angkut(frm) {
		frm.set_value("harga", frm.doc.harga + frm.doc.subsidi_angkut)
	},

	jarak_ring: function (frm) {
		set_jarak_price_list(frm);
	},

	unit: function (frm) {
		set_jarak_price_list(frm);
	}
});

function set_jarak_price_list(frm) {
	if (frm.doc.unit && frm.doc.jarak_ring) {
		// Format: unit - jarak_ring
		let price_list_name = `${frm.doc.unit} - ${frm.doc.jarak_ring}`;

		// Set jarak field with the price list name
		frm.set_value('jarak', price_list_name);

		// Check if price list exists
		frappe.call({
			method: 'frappe.client.get_value',
			args: {
				doctype: 'Price List',
				filters: { name: price_list_name },
				fieldname: 'name'
			},
			callback: function (r) {
				if (!r.message) {
					// Price list doesn't exist, create it
					create_price_list(frm, price_list_name);
				}
			}
		});
	}
}

function create_price_list(frm, price_list_name) {
	frappe.call({
		method: 'frappe.client.insert',
		args: {
			doc: {
				doctype: 'Price List',
				price_list_name: price_list_name,
				enabled: 1,
				buying: 1,
				selling: 0,
				currency: frappe.defaults.get_default('currency') || 'IDR'
			}
		},
		callback: function (r) {
			if (r.message) {
				// frappe.show_alert({
				// 	message: __('Price List "{0}" created successfully', [price_list_name]),
				// 	indicator: 'green'
				// }, 5);
			}
		}
	});
}