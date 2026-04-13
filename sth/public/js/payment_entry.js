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

        if (frm.doc.docstatus == 0) {
            frm.add_custom_button(__("Pilih Nota Piutang"), function () {
                pick_nota_piutang(frm);
            }, __("Buat"));
        }
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
	party_type: function(frm){
		set_no_rekening(frm);
	},
	party: function(frm) {
		// Reset no_kontrak_penjualan jika party berubah
		if (frm.doc.party_type === "Customer") {
			frm.set_value("no_kontrak_penjualan", "");
		}

		set_no_rekening(frm);

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

function set_no_rekening(frm) {

	if (!frm.doc.party || !frm.doc.party_type) {
		frm.set_value("no_rekening", "");
		return;
	}

	frappe.call({
		method: "sth.custom.payment_entry.get_no_rekening",
		args: {
			party_type: frm.doc.party_type,
			party: frm.doc.party
		},
		callback: function(r) {

			if (r.message) {
				frm.set_value("no_rekening", r.message[0]);
				frm.set_value("nama_bank", r.message[1]);
			} else {
				frm.set_value("no_rekening", "");
				frm.set_value("nama_bank", "");
			}
		}
	});

}


function pick_nota_piutang(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __("Pilih Nota Piutang"),
        fields: [
            {
                fieldtype: "Link",
                fieldname: "nota_piutang",
                label: "Nota Piutang",
                options: "Nota Piutang",
                reqd: 1,
                get_query() {
                    return {
                        filters: {
                            tipe: "Pemenuhan Kontrak",
                            docstatus: 1,
                        }
                    };
                }
            }
        ],
        primary_action_label: __("Terapkan"),
        primary_action(values) {
            dialog.hide();
            apply_nota_piutang(frm, values.nota_piutang);
        }
    });
 
    dialog.show();
}
 
async function apply_nota_piutang(frm, nota_piutang_name) {
    try {
        // 1. Fetch Nota Piutang
        const np = await frappe.db.get_doc("Nota Piutang", nota_piutang_name);
 		frm.set_value("unit", np.unit)
        // 2. Kumpulkan semua SI dari kedua table
        const si_from_main = (np.nota_hutang_pemenuhan_kontrak_table || [])
            .filter(row => row.pengakuan_penjualan)
            .map(row => row.pengakuan_penjualan);
 
        const si_from_reclass = (np.reclass_pengakuan_penjualan || [])
            .filter(row => row.pengakuan_penjualan_ppn)
            .map(row => row.pengakuan_penjualan_ppn);
 
        const all_si_names = [...new Set([...si_from_main, ...si_from_reclass])];
 
        if (all_si_names.length === 0) {
            frappe.throw(__("Nota Piutang ini tidak memiliki Sales Invoice."));
        }
 
        // 3. Fetch tiap SI untuk outstanding_amount terkini
        const si_docs = await Promise.all(
            all_si_names.map(name => frappe.db.get_doc("Sales Invoice", name))
        );
 
        // 4. Filter outstanding > 0
        const payable_si = si_docs.filter(si => flt(si.outstanding_amount) > 0);
 
        if (payable_si.length === 0) {
            frappe.throw(__("Semua Sales Invoice pada Nota Piutang ini sudah lunas."));
        }
 
        // 5. Hitung total outstanding
        const total_outstanding = payable_si.reduce(
            (sum, si) => sum + flt(si.outstanding_amount), 0
        );
 
        // 6. Set field nota_piutang_pemenuhan_kontrak
        frm.set_value("nota_piutang_pemenuhan_kontrak", np.name);
 
        // 7. Set party dari SI pertama jika belum diisi
        if (!frm.doc.party) {
            await frm.set_value("party_type", "Customer");
            await frm.set_value("party", payable_si[0].customer);
        }
 
        // 8. Set bank account dari Unit
        if (np.unit) {
            const unit_doc = await frappe.db.get_doc("Unit", np.unit);
            if (unit_doc.bank_account) {
                await frm.set_value("paid_to", unit_doc.bank_account);
            }
        }
 
        // 9. Kosongkan references lama lalu isi yang baru
        frm.clear_table("references");
 
        for (const si of payable_si) {
            const row = frm.add_child("references");
            row.reference_doctype = "Sales Invoice";
            row.reference_name = si.name;
            row.bill_no = si.bill_no || "";
            row.due_date = si.due_date;
            row.total_amount = flt(si.grand_total);
            row.outstanding_amount = flt(si.outstanding_amount);
            row.allocated_amount = flt(si.outstanding_amount);
        }
 
        frm.refresh_field("references");
 
        // 10. Recalculate paid_amount & received_amount
        frm.set_value("paid_amount", total_outstanding);
        frm.set_value("received_amount", total_outstanding);
 
        frappe.show_alert({
            message: __(`Nota Piutang <b>${np.name}</b> berhasil diterapkan.`),
            indicator: "green"
        }, 4);
 
    } catch (err) {
        frappe.msgprint({
            title: __("Error"),
            message: err.message || JSON.stringify(err),
            indicator: "red"
        });
    }
}