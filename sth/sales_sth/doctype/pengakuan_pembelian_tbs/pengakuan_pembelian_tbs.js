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

		frm.get_field("items").grid.cannot_add_rows = true;
		frm.get_field("items").grid.wrapper
			.find('.grid-add-row')
			.hide();
		frm.get_field("items").grid.wrapper
			.find('.grid-remove-rows')
			.hide();
		frm.refresh_field("items");

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

				update_subsidi_angkut_child(frm);
				calculate_parent_totals(frm);
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
		update_subsidi_angkut_child(frm);
	},

	jarak_ring: function (frm) {
		set_jarak_price_list(frm);
	},

	unit: function (frm) {
		set_jarak_price_list(frm);
	}
});

function update_subsidi_angkut_child(frm) {
    if (frm.doc.items && frm.doc.items.length > 0) {
        frm.doc.items.forEach(function(row) {
            frappe.model.set_value(row.doctype, row.name, "subsidi_angkut", frm.doc.subsidi_angkut);

            let rate = flt(row.rate);
            let bonus = flt(row.bonus);
            let subsidi = flt(frm.doc.subsidi_angkut);  
            let terima = flt(row.terima);
            let percent_pph22 = flt(row.percent_pajak_pph_22);

            let total_seluruhnya = (rate + bonus + subsidi) * terima;
            frappe.model.set_value(row.doctype, row.name, "total_seluruhnya", total_seluruhnya);
            frappe.model.set_value(row.doctype, row.name, "rupiah_pajak_pph_22", total_seluruhnya * percent_pph22 / 100);
            frappe.model.set_value(row.doctype, row.name, "total", total_seluruhnya - (total_seluruhnya * percent_pph22 / 100));
        });
    }
    frm.refresh_field("items");
}

function set_jarak_price_list(frm) {
	if (!frm.doc.unit) return;

	const jarakRing = (frm.doc.jarak_ring || "").trim();
	const finalRing = jarakRing ? jarakRing : "TANPA RING";

	let price_list_name = `${frm.doc.unit} - ${finalRing}`;

	frm.set_value('jarak', price_list_name);

	frappe.call({
		method: 'frappe.client.get_value',
		args: {
			doctype: 'Price List',
			filters: { name: price_list_name },
			fieldname: 'name'
		},
		callback: function (r) {
			if (!r.message) {
				create_price_list(frm, price_list_name);
			}
		}
	});
}

function resolve_price_list(frm) {
	if (!frm.doc.unit) return "";

	const jarak = (frm.doc.jarak || "").trim();
	const finalJarak = jarak ? jarak : "TANPA RING";

	return `${frm.doc.unit} - ${finalJarak}`;
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

function calculate_parent_totals(frm) {

    let total_bruto = 0;
    let total_tarra = 0;
    let total_netto = 0;
    let total_potkg = 0;
    let total_terima = 0;
    let total_pembayaran = 0;
    let total_bonus = 0;
    let total_seluruhnya = 0;
	let total_pajak_pph_22 = 0;

    if (frm.doc.items && frm.doc.items.length > 0) {

        frm.doc.items.forEach(function(row) {
            total_bruto += flt(row.bruto);
            total_tarra += flt(row.tarra);
            total_netto += flt(row.netto);
            total_potkg += flt(row.pot);
            total_terima += flt(row.terima);
            total_bonus += flt(row.bonus)*flt(row.terima);
            total_seluruhnya += flt(row.total_seluruhnya);
            total_pembayaran += flt(row.total); 
			total_pajak_pph_22 += flt(row.rupiah_pajak_pph_22); 
        });

    }

    frm.set_value("total_bruto", total_bruto);
    frm.set_value("total_tarra", total_tarra);
    frm.set_value("total_netto", total_netto);
    frm.set_value("total_potkg", total_potkg);
    frm.set_value("total_terima", total_terima);
    frm.set_value("total_bonus", total_bonus);
    frm.set_value("total_seluruhnya", total_seluruhnya);
    frm.set_value("total_pembayaran_ke_supplier", total_pembayaran);
	frm.set_value("total_pajak_pph_22", total_pajak_pph_22);
}