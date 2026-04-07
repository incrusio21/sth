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
				if (accounts && accounts.length) {
					frm.set_value("paid_from", accounts[0].name);
				} else {
					frappe.msgprint("Akun 'Uang Muka Penjualan' tidak ditemukan.");
				}
			});

			frappe.db.get_doc("Company", frm.doc.company).then(company => {
				if (company.default_cash_account) {
					frm.set_value("paid_to", company.default_cash_account);
				} else {
					frappe.msgprint("Default Cash Account tidak ditemukan di Company.");
				}
			});

			const first_term = so.payment_schedule && so.payment_schedule[0];
			if (!first_term) {
				frappe.msgprint("Tidak ada payment schedule di Sales Order ini.");
				return;
			}

			const nilai_dp = first_term.payment_amount;

			frm.set_value("paid_amount", nilai_dp);
			frm.set_value("received_amount", nilai_dp);

			frappe.db.get_list("Sales Taxes and Charges Template", {
				filters: {
					company: frm.doc.company,
					title: ["like", "%Excluding PPN%"],
					disabled: 0,
				},
				limit: 1,
			}).then(templates => {
				if (!templates || !templates.length) {
					frappe.msgprint("Template 'Excluding PPN' tidak ditemukan.");
					return;
				}

				frappe.db.get_doc("Sales Taxes and Charges Template", templates[0].name).then(template_doc => {
				    console.log("full template doc:", template_doc);
				    console.log("taxes rows:", template_doc.taxes);
				    if (template_doc.taxes && template_doc.taxes[0]) {
				        console.log("first tax row keys:", Object.keys(template_doc.taxes[0]));
				    }
				});

				frappe.db.get_doc("Sales Taxes and Charges Template", templates[0].name).then(template_doc => {
					let taxes = template_doc.taxes
					if (!taxes || !taxes.length) {
						frappe.msgprint("Tidak ada baris pajak di template PPN.");
						return;
					}
					frm.clear_table("deductions");

					let ppn_total = 0;

					taxes.forEach(tax => {
						const amount = tax.tax_amount || (nilai_dp * tax.rate / 100);
						ppn_total += amount;

						frappe.db.get_value("Company", frm.doc.company, "cost_center").then(r => {
							const cost_center = r.message && r.message.cost_center;
							frm.add_child("deductions", {
								account: tax.account_head,
								cost_center: cost_center,
								amount: amount * -1,
							});
							frm.refresh_field("deductions");

							// Update paid_amount & received_amount = nilai_dp + ppn
							const total = nilai_dp + ppn_total;
							frm.set_value("paid_amount", total);
							frm.set_value("received_amount", total);
						});
					});
				});
			});
		});
	},
});