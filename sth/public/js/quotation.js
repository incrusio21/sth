frappe.ui.form.on('Quotation', {
	party_name: function (frm) {
		set_komoditi_filter(frm);

		if (frm.doc.komoditi) {
			frm.set_value('komoditi', '');
			frm.clear_table('keterangan_per_komoditi');
			frm.refresh_field('keterangan_per_komoditi');
		}

		frappe.db.get_doc('Customer', frm.doc.party_name).then((res) => {
			frm.set_value('penandatangan_buyer', res.penandatangan);
			frm.set_value('jabatan_buyer', res.jabatan_penandatangan);

			frm.refresh_field('penandatangan_buyer');
			frm.refresh_field('jabatan_buyer');
		});
	},
	refresh: function (frm) {
		set_komoditi_filter(frm);
		frm.set_df_property('valid_till', 'hidden', 1);
		set_query_unit(frm)
		set_rekening_filter(frm)
	},
	komoditi: function (frm) {
		if (frm.doc.komoditi && frm.doc.party_name && frm.doc.quotation_to == "Customer") {
			validate_komoditi(frm);
		}

		if (frm.doc.komoditi) {
			frm.clear_table('keterangan_per_komoditi');

			frappe.call({
				method: 'frappe.client.get',
				args: {
					doctype: 'Komoditi',
					name: frm.doc.komoditi
				},
				callback: function (r) {
					if (r.message && r.message.keterangan_per_komoditi) {
						r.message.keterangan_per_komoditi.forEach(function (row) {
							let child_row = frm.add_child('keterangan_per_komoditi');
							child_row.keterangan = row.keterangan;
							child_row.parameter = row.parameter;
						});

						frm.refresh_field('keterangan_per_komoditi');
					}
				}
			});
		}
	},
	onload: function (frm) {
		set_query_unit(frm)
	},
	company: function (frm) {
		set_query_unit(frm)
		set_rekening_filter(frm)
	},
	unit: function (frm) {
		set_rekening_filter(frm)
	},
	komoditi: function (frm) {
		frappe.db.get_doc("Unit", frm.doc.unit).then(doc => {
			const catatan = `${frm.doc.komoditi} yang dijual adalah produksi perusahaan kami yang berasal dari ${frm.doc.company} dan lokasi ${doc.address}`;
			frm.set_value("catatan", doc.address ? catatan : "");
			frm.refresh_field("catatan");
		})
	}
});

function set_rekening_filter(frm) {
	frm.set_query('no_rekening_tujuan', function () {
		return {
			filters: {
				'company': ['=', frm.doc.company],
				// 'unit': ['=', frm.doc.unit],

			}
		};
	});
}

function set_komoditi_filter(frm) {
	if (frm.doc.quotation_to == "Customer" && frm.doc.party_name) {
		frappe.call({
			method: 'frappe.client.get',
			args: {
				doctype: 'Customer',
				name: frm.doc.party_name
			},
			callback: function (r) {
				if (r.message && r.message.custom_customer_komoditi) {
					let komoditi_list = r.message.custom_customer_komoditi.map(function (row) {
						return row.komoditi;
					});

					if (komoditi_list.length > 0) {
						frm.set_query('komoditi', function () {
							return {
								filters: {
									'name': ['in', komoditi_list]
								}
							};
						});
					} else {
						frm.set_query('komoditi', function () {
							return {
								filters: {
									'name': ['in', []]
								}
							};
						});
					}
				}
			}
		});
	} else {
		frm.set_query('komoditi', function () {
			return {};
		});
	}
}

function validate_komoditi(frm) {
	if (!frm.doc.quotation_to == "Customer") {
		return;
	}

	if (!frm.doc.party_name) {
		return;
	}

	frappe.call({
		method: 'frappe.client.get',
		args: {
			doctype: 'Customer',
			name: frm.doc.party_name
		},
		callback: function (r) {
			if (r.message && r.message.custom_customer_komoditi) {
				let komoditi_list = r.message.custom_customer_komoditi.map(function (row) {
					return row.komoditi;
				});

				if (!komoditi_list.includes(frm.doc.komoditi)) {
					frappe.msgprint({
						title: __('Invalid Komoditi'),
						indicator: 'red',
						message: __('The selected Komoditi "{0}" is not linked to Customer "{1}". Please select a valid Komoditi.', [frm.doc.komoditi, frm.doc.party_name])
					});
					frm.set_value('komoditi', '');
				}
			}
		}
	});
}


function set_query_unit(frm) {
	frm.set_query('unit', function () {
		return {
			filters: {
				'company': frm.doc.company
			}
		};
	});
}