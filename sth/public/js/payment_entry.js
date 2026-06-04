frappe.ui.form.on("Payment Entry", {
	setup(frm) {

		frm.set_query('path', function() {
			return {
				filters: {
					disabled: 0
				}
			};
		});

	},
	// before_submit(frm) {
	// 	return check_mandiri_kcm_warning(frm);
	// },
	before_workflow_action: async function(frm) {
		if (
			frm.doc.workflow_state === "Butuh Persetujuan 2" &&
			frm.selected_workflow_action === "Approve"
		) {
			await check_mandiri_kcm_warning(frm);
		}
	},
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

		check_mandiri_kcm(frm);
		// make_pdo_preview(frm)
	},
	paid_from: function(frm){
		check_mandiri_kcm(frm);
		set_ft_service(frm);
	},
	paid_to: function(frm){
		set_ft_service(frm);
	},
	ft_service: function(frm) {
		if (frm.doc.ft_service === "UBP") {
			frm.set_value("path", "MCM_BillPaymentSingle");
		} else {
			frm.set_value("path", "MCM_SingleMix");
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

	unit: function(frm){
		pasang_company_account(frm);
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
	no_payroll_entry(frm) {
        if (!frm.doc.no_payroll_entry) return;

        frappe.call({
            // Sesuaikan path method dengan lokasi file kamu
            method: "sth.overrides.payroll_entry.get_payroll_entry_for_payment",
            args: { payroll_entry: frm.doc.no_payroll_entry },
            freeze: true,
            freeze_message: __("Mengambil data Payroll Entry..."),
            callback(r) {
                if (!r.message) return;

                const d = r.message;

                // Set payment type paksa Internal Transfer
                frm.set_value("payment_type", "Internal Transfer");

                // Auto-fill field dari Payroll Entry
                frm.set_value("company",                  d.company);
                frm.set_value("paid_to",                  d.paid_to);
                frm.set_value("paid_to_account_currency", d.paid_to_account_currency);
                frm.set_value("paid_amount",              d.paid_amount);
                frm.set_value("received_amount",          d.received_amount);
                frm.set_value("remarks",                  d.remarks);

                if (d.cost_center) {
                    frm.set_value("cost_center", d.cost_center);
                }
            }
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

	let paid_to = null;

	if (frm.doc.payment_type === "Internal Transfer") {
		paid_to = frm.doc.paid_to;
	}

	frappe.call({
		method: "sth.custom.payment_entry.get_no_rekening",
		args: {
			party_type: frm.doc.party_type,
			party: frm.doc.party,
			paid_to: paid_to,
			tipe_transfer: frm.doc.tipe_transfer,
			permintaan_dana_operasional: frm.doc.permintaan_dana_operasional,
			payment_type: frm.doc.payment_type
		},
		callback: function(r) {

			if (r.message) {

				frm.set_value(
					"no_rekening",
					r.message.no_rekening || ""
				);

				frm.set_value(
					"nama_bank",
					r.message.nama_bank || ""
				);

				frm.set_value(
					"no_rekening_tujuan",
					r.message.no_rekening_tujuan || ""
				);

				frm.set_value(
					"bank_tujuan",
					r.message.bank_tujuan || ""
				);

			} else {

				frm.set_value("no_rekening", "");
				frm.set_value("nama_bank", "");
				frm.set_value("no_rekening_tujuan", "");
				frm.set_value("bank_tujuan", "");
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

function pasang_company_account(frm){
	if (frm.doc.unit) {
		frappe.db.get_value('Unit', frm.doc.unit, 'default_bank_account', function(r) {
			if (r && r.default_bank_account) {
				frm.set_value('bank_account', r.default_bank_account);
			} else {
				frm.set_value('bank_account', '');
			}
		});
	} else {
		frm.set_value('bank_account', '');
	}
}

function make_pdo_preview(frm){
	const rows = frm.doc.payment_voucher_kas_pdo || [];
	if (rows.length === 0) return;

	const uniquePDO = [...new Set(
		rows
			.map(r => r.no_pdo)
			.filter(v => v && v.trim() !== '')
	)];

	if (uniquePDO.length === 0) return;

	frm.add_custom_button(__('Check Preview'), function() {
		show_pdo_preview(uniquePDO);
	}, __('PDO'));
}

function show_pdo_preview(pdoList) {
	const baseUrl = 'https://sth.digitalasiasolusindo.com/printview'
		+ '?doctype=Permintaan%20Dana%20Operasional'
		+ '&format=PF%20Preview%20PDO'
		+ '&no_letterhead=0'
		+ '&trigger_print=0';

	let html = '<div style="display:flex; flex-direction:column; gap:10px; padding: 10px 0;">';

	pdoList.forEach(pdo => {
		const url = `${baseUrl}&name=${encodeURIComponent(pdo)}`;
		html += `
			<div style="display:flex; justify-content:space-between; align-items:center; 
						padding: 10px 14px; border: 1px solid #d1d8dd; border-radius: 6px;">
				<span style="font-weight:500;">${frappe.utils.escape_html(pdo)}</span>
				<a href="${url}" target="_blank" class="btn btn-sm btn-primary">
					<i class="fa fa-external-link"></i>&nbsp; Open Preview
				</a>
			</div>`;
	});

	html += '</div>';

	new frappe.ui.Dialog({
		title: __('PDO Preview'),
		fields: [{
			fieldtype: 'HTML',
			fieldname: 'preview_html',
			options: html
		}]
	}).show();
}

function check_mandiri_kcm(frm) {

	if (!frm.doc.paid_from) {

		frm.set_df_property(
			'mandiri_kcm',
			'hidden',
			1
		);

		return;
	}

	frappe.call({
		method: 'sth.custom.payment_entry.is_mandiri_kcm',
		args: {
			account: frm.doc.paid_from
		},
		callback: function(r) {

			let is_mandiri_kcm = r.message ? 0 : 1;

			frm.set_df_property(
				'mandiri_kcm',
				'hidden',
				is_mandiri_kcm
			);
		}
	});
}

async function set_ft_service(frm) {

	let paid_from = frm.doc.paid_from;

	if (!paid_from) {
		return;
	}

	try {

		let from_bank_account = await frappe.db.get_value(
			'Bank Account',
			{ account: paid_from },
			['bank']
		);

		let from_bank = from_bank_account.message?.bank;

		if (!from_bank) {

			frm.set_value(
				'ft_service',
				'InHouse Transfer'
			);

			return;
		}

		let rekening = await frappe.call({
			method: "sth.custom.payment_entry.get_no_rekening",
			args: {
				party_type: frm.doc.party_type,
				party: frm.doc.party,
				paid_to: frm.doc.payment_type === "Internal Transfer"
					? frm.doc.paid_to
					: null
			}
		});

		let to_bank =
			rekening.message?.bank_tujuan ||
			rekening.message?.nama_bank;

		if (!to_bank) {

			frm.set_value(
				'ft_service',
				'InHouse Transfer'
			);

			return;
		}

		frm.set_value(
			'ft_service',
			from_bank !== to_bank
				? 'Online Domestic Transfer'
				: 'InHouse Transfer'
		);

	}

	catch (e) {

		console.log(e);

		frm.set_value(
			'ft_service',
			'InHouse Transfer'
		);

	}
}

async function check_mandiri_kcm_warning(frm) {

    let r = await frappe.call({
        method: "sth.bank_payment.custom.payment_entry.get_mandiri_kcm_warnings",
        args: {
            payment_entry: frm.doc.name
        }
    });

    let data = r.message || {};

    if (!data.has_warning) {
        return;
    }

    const field_labels = {
        beneficiary_account: "beneficiary_account / No Rekening Tujuan",
        debit_account: "debit_account / No Rekening",
        beneficiary_name: "beneficiary_name / Nama Penerima",
        bank_code: "bank_code / Kode Bank",
        amount: "amount / Nominal",
        currency: "currency / Mata Uang"
    };

    let missing_fields = (data.missing_fields || []).map(
        field => field_labels[field] || field
    );

    return new Promise((resolve, reject) => {

		// console.log("freeze count", frappe.dom.freeze_count);

		frappe.dom.unfreeze();

		// console.log("after unfreeze", frappe.dom.freeze_count);

		frappe.confirm(
			`
			Mandatory field Mandiri KCM belum lengkap:
			<br><br>
			<b>${missing_fields.join("<br>")}</b>
			<br><br>
			Proses Mandiri KCM kemungkinan gagal.
			<br><br>
			Apakah Anda ingin melanjutkan?
			`,
			() => resolve(),
			async () => {
				await frm.reload_doc();
				reject();
			}
		);

	});

}