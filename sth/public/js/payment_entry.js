frappe.ui.form.on("Payment Entry", {
	refresh: function(frm) {
		frm.set_query("no_kontrak_penjualan", function() {
			return {
				filters: {
					customer: frm.doc.party || "",
					docstatus: 1,
					per_billed: ["<", 100],
					company: frm.doc.company
				},
			};
		});
	},

	company: function(frm) {
		frm.set_query("no_kontrak_penjualan", function() {
			return {
				filters: {
					customer: frm.doc.party || "",
					docstatus: 1,
					per_billed: ["<", 100],
					company: frm.doc.company
				},
			};
		});
	},

	party: function(frm) {
		// Reset no_kontrak_penjualan jika party berubah
		if (frm.doc.party_type === "Customer") {
			frm.set_value("no_kontrak_penjualan", "");
		}

		// Re-apply filter dengan customer baru
		frm.set_query("no_kontrak_penjualan", function() {
			return {
				filters: {
					customer: frm.doc.party || "",
					docstatus: 1,
					per_billed: ["<", 100],
					company: frm.doc.company
				},
			};
		});
	},
	no_kontrak_penjualan: function(frm) {
		if (!frm.doc.no_kontrak_penjualan) return;
		frm.set_value("paid_from", "");
		frappe.db.get_doc("Sales Order", frm.doc.no_kontrak_penjualan).then(so => {
			// 1. Set customer sebagai party
			frm.set_value("party_type", "Customer");
			frm.set_value("party", so.customer);

			frappe.db.get_list("Account", {
				filters: {
					company: frm.doc.company,
					account_name: ["like", "%Uang Muka Penjualan%"],
					is_group: 0,
				},
				fields: ["name"],
				limit: 1,
			}).then(accounts => {
				frm.set_value("paid_from", accounts[0].name);
				
			});

			const first_term = so.payment_schedule && so.payment_schedule[0];
			if (!first_term) {
				frappe.msgprint("Tidak ada payment schedule di Sales Order ini.");
				return;
			}

			let nilai_dp = first_term.payment_amount;

			frm.set_value("paid_amount", nilai_dp);
			frm.set_value("received_amount", nilai_dp);

			category_tax = "%Excluding PPN%"
			if(so.taxes){
				if(so.taxes[0].included_in_print_rate == 1){
					category_tax = "%Including PPN%"
				}
			}

			frappe.db.get_list("Sales Taxes and Charges Template", {
				filters: {
					company: frm.doc.company,
					title: ["like", category_tax],
					disabled: 0,
				},
				limit: 1,
			}).then(templates => {
				if (!templates || !templates.length) {
					frappe.msgprint("Template PPN tidak ditemukan.");
					return;
				}

				frappe.db.get_doc("Sales Taxes and Charges Template", templates[0].name).then(template_doc => {
					let taxes = template_doc.taxes;
					if (!taxes || !taxes.length) {
						frappe.msgprint("Tidak ada baris pajak di template PPN.");
						return;
					}

					frm.clear_table("deductions");
					let ppn_total = 0;
					const is_inclusive = so.taxes && so.taxes[0] && so.taxes[0].included_in_print_rate == 1;

					taxes.forEach(tax => {
						let amount;
						if (is_inclusive) {
							// Kalau inclusive: ekstrak PPN dari nilai_dp
							const dpp = nilai_dp / (1 + tax.rate / 100);
							amount = nilai_dp - dpp;
						} else {
							// Kalau exclusive: PPN ditambahkan di atas nilai_dp
							amount = nilai_dp * tax.rate / 100;
						}
						ppn_total += amount;

						frappe.db.get_value("Company", frm.doc.company, "cost_center").then(r => {
							const cost_center = r.message && r.message.cost_center;
							frm.add_child("deductions", {
								account: tax.account_head,
								cost_center: cost_center,
								amount: amount * -1,
							});
							frm.refresh_field("deductions");

							if (is_inclusive) {
								// Paid amount tetap nilai_dp (sudah include PPN)
								frm.set_value("paid_amount", nilai_dp);
								frm.set_value("received_amount", nilai_dp);
							} else {
								// Paid amount = nilai_dp + PPN
								const total = nilai_dp + ppn_total;
								frm.set_value("paid_amount", total);
								frm.set_value("received_amount", total);
							}
						});
					});
				});
			});
		});
	},
});