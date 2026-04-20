frappe.ui.form.on('Nota Piutang', {
	setup: function(frm) {
		frm.set_query('akun_reclass', 'reclass_pengakuan_penjualan', function() {
			return {
				query: 'sth.accounting_sth.doctype.nota_piutang.nota_piutang.get_akun_reclass',
				filters: { company: frm.doc.company }
			};
		});
		frm.fields_dict['reclass_pengakuan_penjualan'].grid.cannot_add_rows = true;
	},

	refresh: function(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.tipe === "Pemenuhan Kontrak") {
			frm.add_custom_button(__("Pembayaran ke PV"), function () {
				make_payment_entry(frm);
			}, __("Buat"));
		}
		setup_filter(frm);
	},

	company: function(frm) {
		setup_filter(frm);
	},

	no_kontrak: function(frm) {
		if (!frm.doc.no_kontrak) return;

		frappe.db.get_doc('Sales Order', frm.doc.no_kontrak)
			.then(so => {
				frm.set_value('company', so.company);

				if (so.payment_schedule && so.payment_schedule.length > 0) {
					frm.set_value('nilai_dp', so.payment_schedule[0].payment_amount);
				}

				if (so.unit) {
					frm.set_value('unit', so.unit);
					frappe.db.get_doc('Unit', so.unit)
						.then(unit_doc => {
							if (unit_doc.bank_account) {
								frm.set_value('akun_kas_bank', unit_doc.bank_account);
							}
						})
						.catch(() => {
							frappe.msgprint(__('Unit {0} tidak ditemukan.', [so.unit]));
						});
				}

				// Jika tipe Pemenuhan Kontrak, cek DP dulu sebelum dialog bulan
				if (frm.doc.tipe === 'Pemenuhan Kontrak') {
					cek_dp_lalu_dialog(frm);
				}
			})
			.catch(() => {
				frappe.msgprint(__('Sales Order {0} tidak ditemukan.', [frm.doc.no_kontrak]));
			});
	},

	tipe: function(frm) {
		if (frm.doc.tipe === 'Pemenuhan Kontrak' && frm.doc.no_kontrak) {
			cek_dp_lalu_dialog(frm);
		}
	}
});

// ── Cek sisa DP, kalau sudah habis tampilkan dialog bulan ──────────────
function cek_dp_lalu_dialog(frm) {
	if (!frm.doc.no_kontrak) return;

	frappe.call({
		method: 'sth.accounting_sth.doctype.nota_piutang.nota_piutang.get_sisa_dp',
		args: { no_kontrak: frm.doc.no_kontrak },
		callback: function(r) {
			if (r.exc) return;

			const sisa_dp = r.message || 0;

			if (sisa_dp > 0) {
				// Masih ada DP yang belum terpakai → warning, hentikan proses
				frappe.msgprint({
					title: __('DP Belum Selesai'),
					message: __(
						'Masih ada DP yang belum selesai dipakai (sisa: {0}). ' +
						'Buat Pengakuan Penjualan untuk DP terlebih dahulu sebelum melanjutkan.',
						[format_currency(sisa_dp, frm.doc.currency || 'IDR')]
					),
					indicator: 'orange'
				});
				return;
			}

			// DP sudah habis → lanjut ke dialog pilih bulan
			tampilkan_dialog_bulan(frm);
		}
	});
}

// ── Tampilkan dialog pilih bulan dari SI yang tersedia ─────────────────
function tampilkan_dialog_bulan(frm) {
	frappe.call({
		method: 'sth.accounting_sth.doctype.nota_piutang.nota_piutang.get_si_pengiriman',
		args: {
			no_kontrak: frm.doc.no_kontrak,
			bulan: null  // tanpa filter bulan, untuk dapat semua pilihan
		},
		callback: function(r) {
			if (!r.message || r.message.length === 0) {
				frappe.msgprint({
					title: __('Tidak Ada SI'),
					message: __('Tidak ada Sales Invoice Pengiriman yang tersedia untuk kontrak ini.'),
					indicator: 'red'
				});
				return;
			}

			// Kumpulkan distinct bulan dari posting_date
			const bulan_map = {};
			const month_names = [
				'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
				'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
			];

			r.message.forEach(si => {
				const d = new Date(si.posting_date);
				const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
				bulan_map[key] = `${month_names[d.getMonth()]} ${d.getFullYear()}`;
			});

			const bulan_options = Object.keys(bulan_map).sort().map(key => ({
				value: key,
				label: bulan_map[key]
			}));

			const dialog = new frappe.ui.Dialog({
				title: __('Pilih Bulan SI Pengiriman'),
				fields: [
					{
						fieldname: 'bulan',
						fieldtype: 'Select',
						label: __('Bulan'),
						options: bulan_options.map(b => b.label).join('\n'),
						reqd: 1
					}
				],
				primary_action_label: __('Pilih'),
				primary_action(values) {
					const selected = bulan_options.find(b => b.label === values.bulan);
					if (selected) {
						fetch_si_pengiriman(frm, selected.value);
					}
					dialog.hide();
				}
			});

			dialog.show();
		}
	});
}

// ── Fetch SI per bulan dan isi tabel ──────────────────────────────────
function fetch_si_pengiriman(frm, bulan) {
	if (!frm.doc.no_kontrak) {
		frappe.msgprint(__('Pilih No. Kontrak terlebih dahulu.'));
		return;
	}

	frm.set_value("bulan", bulan)

	frappe.call({
		method: 'sth.accounting_sth.doctype.nota_piutang.nota_piutang.get_si_pengiriman',
		args: {
			no_kontrak: frm.doc.no_kontrak,
			bulan: bulan || null
		},
		callback: function(r) {
			if (!r.message || r.message.length === 0) {
				frappe.msgprint({
					title: __('Tidak Ada SI'),
					message: __('Tidak ada Sales Invoice Pengiriman untuk bulan ini, ' +
								'atau semua SI sudah dipakai di Nota Piutang lain.'),
					indicator: 'red'
				});
				return;
			}

			frm.clear_table('nota_hutang_pemenuhan_kontrak_table');

			r.message.forEach(si => {
				let row = frm.add_child('nota_hutang_pemenuhan_kontrak_table');
				row.pengakuan_penjualan = si.name;
				row.qty                 = si.qty;
				row.rate                = si.rate;
				row.subtotal            = si.subtotal;
				row.posting_date        = si.posting_date;
				row.outstanding_amount  = si.outstanding_amount;
			});

			frm.refresh_field('nota_hutang_pemenuhan_kontrak_table');
			fetch_nilai_kontrak(frm);
		}
	});
}

// ── (tidak berubah) ────────────────────────────────────────────────────
function setup_filter(frm) {
	frm.set_query('no_kontrak', function() {
		return {
			filters: [
				['Sales Order', 'docstatus', '=', 1],
				['Sales Order', 'per_billed', '<', 100]
			]
		};
	});
	frm.set_query('akun_uang_muka', function() {
		return {
			filters: [
				['Account', 'is_group', '=', 0],
				['Account', 'name', 'like', "%uang muka penjualan%"],
				['Account', 'company', '=', frm.doc.company]
			]
		};
	});
	frm.set_query('akun_kas_bank', function() {
		return {
			filters: [
				['Account', 'is_group', '=', 0],
				['Account', 'account_type', 'in', ["Cash","Bank"]],
				['Account', 'company', '=', frm.doc.company]
			]
		};
	});
}

function fetch_nilai_kontrak(frm) {
	if (!frm.doc.no_kontrak) return;

	// Kumpulkan semua pengakuan_penjualan dari tabel (filter kosong)
	const pengakuan_list = (frm.doc.nota_hutang_pemenuhan_kontrak_table || [])
		.map(row => row.pengakuan_penjualan)
		.filter(v => !!v);

	// Step 1: Ambil data kontrak (nilai_kontrak, dpp, ppn, tax_rate)
	frappe.call({
		method: 'sth.accounting_sth.doctype.nota_piutang.nota_piutang.get_nilai_kontrak',
		args: { no_kontrak: frm.doc.no_kontrak },
		callback: function(r) {
			if (!r.message) return;
			const d = r.message;

			frm.set_value('nilai_kontrak', d.nilai_kontrak);
			frm.set_value('dpp',           d.dpp);
			frm.set_value('ppn',           d.ppn);

			const table_total = (frm.doc.nota_hutang_pemenuhan_kontrak_table || [])
				.reduce((sum, row) => sum + (row.outstanding_amount || 0), 0);

			// Step 2: Ambil dp_dpp & dp_ppn dari JE DP
			frappe.call({
				method: 'sth.accounting_sth.doctype.nota_piutang.nota_piutang.get_dp_from_je',
				args: {
					no_kontrak:      frm.doc.no_kontrak,
					pengakuan_list:  JSON.stringify(pengakuan_list),
				},
				callback: function(r2) {
					const dp     = r2.message || {};
					const dp_dpp = dp.dp_dpp  || 0;
					const dp_ppn = dp.dp_ppn  || 0;

					frm.set_value('dp_dpp',   dp_dpp);
					frm.set_value('dp_ppn',   dp_ppn);
					frm.set_value('total_dp', dp_dpp + dp_ppn);

					let sisa_dpp = table_total;
					let sisa_ppn = sisa_dpp * d.tax_rate_total;

					frm.set_value('sisa_dpp', sisa_dpp < 0 ? 0 : sisa_dpp);
					frm.set_value('sisa_ppn', sisa_ppn < 0 ? 0 : sisa_ppn);

					build_reclass_table(frm, d.tax_rate_total);
				}
			});
		}
	});
}

function build_reclass_table(frm, tax_rate_total) {
	const rows = frm.doc.nota_hutang_pemenuhan_kontrak_table || [];
	if (!rows.length) return;

	const groups = {};
	rows.forEach(row => {
		if (!row.posting_date) return;
		const d   = frappe.datetime.str_to_obj(row.posting_date);
		const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
		if (!groups[key]) groups[key] = { rows: [], posting_date: row.posting_date };
		groups[key].rows.push(row);
	});

	let dp_remaining = frm.doc.sisa_dpp || 0;
	const reclass_rows = [];

	if (dp_remaining == 0) {
		frappe.throw("Nota Bulan ini tidak perlu dibayarkan lagi, silahkan masukkan bulan yang lain untuk pengambilan Pengakuan Penjualan.");
	}

	Object.keys(groups).sort().forEach(key => {
		const grp          = groups[key];
		const sum_subtotal = grp.rows.reduce((s, r) => s + (r.outstanding_amount || 0), 0);
		const sum_qty      = grp.rows.reduce((s, r) => s + (r.qty     || 0), 0);
		const avg_rate     = grp.rows.reduce((s, r) => s + (r.rate    || 0), 0) / grp.rows.length;

		const net_subtotal = sum_subtotal;

		if (net_subtotal <= 0) return;

		const [year, month] = key.split('-');
		const month_name    = new Date(year, parseInt(month) - 1, 1)
			.toLocaleString('id-ID', { month: 'long', year: 'numeric' });

		const ppn         = net_subtotal * tax_rate_total;
		const grand_total = net_subtotal + ppn;

		reclass_rows.push({
			periode:     month_name,
			qty:         sum_qty,
			rate:        avg_rate,
			subtotal:    net_subtotal,
			ppn:         ppn,
			grand_total: grand_total,
		});
	});

	frm.clear_table('reclass_pengakuan_penjualan');

	reclass_rows.forEach(data => {
		const row       = frm.add_child('reclass_pengakuan_penjualan');
		row.periode     = data.periode;
		row.qty         = data.qty;
		row.rate        = data.rate;
		row.subtotal    = data.subtotal;
		row.ppn         = data.ppn;
		row.grand_total = data.grand_total;
	});

	frm.refresh_field('reclass_pengakuan_penjualan');
	frm.fields_dict['reclass_pengakuan_penjualan'].grid.cannot_add_rows = true;
	frm.fields_dict['reclass_pengakuan_penjualan'].grid.refresh();
}

async function make_payment_entry(frm) {
	try {
		if (!frm.doc.unit) {
			frappe.throw(__("Field Unit kosong, tidak bisa mengambil akun bank."));
		}

		const unit_doc     = await frappe.db.get_doc("Unit", frm.doc.unit);
		const bank_account = unit_doc.bank_account;
		if (!bank_account) {
			frappe.throw(__("Doctype Unit tidak memiliki field bank_account yang terisi."));
		}

		// ── SI dari main table ─────────────────────────────────────────
		const si_names = (frm.doc.nota_hutang_pemenuhan_kontrak_table || [])
			.filter(row => row.pengakuan_penjualan)
			.map(row => row.pengakuan_penjualan);

		// ── JE dari reclass table ──────────────────────────────────────
		const je_names = (frm.doc.reclass_pengakuan_penjualan || [])
			.filter(row => row.pengakuan_penjualan_ppn)
			.map(row => row.pengakuan_penjualan_ppn);

		if (si_names.length === 0 && je_names.length === 0) {
			frappe.throw(__("Tidak ada Sales Invoice maupun Journal Entry di tabel."));
		}

		// ── Fetch docs paralel ─────────────────────────────────────────
		const [si_docs, je_docs] = await Promise.all([
			si_names.length ? Promise.all(si_names.map(n => frappe.db.get_doc("Sales Invoice", n))) : [],
			je_names.length ? Promise.all(je_names.map(n => frappe.db.get_doc("Journal Entry", n)))  : [],
		]);

		const payable_si = si_docs.filter(si => flt(si.outstanding_amount) > 0);
		const payable_je = je_docs.filter(je => flt(je.total_debit) > 0);

		if (payable_si.length === 0 && payable_je.length === 0) {
			frappe.throw(__("Semua tagihan sudah lunas."));
		}

		// ── Validasi company konsisten ─────────────────────────────────
		const all_companies = [
			...payable_si.map(d => d.company),
			...payable_je.map(d => d.company),
		];
		if ([...new Set(all_companies)].length > 1) {
			frappe.throw(__("Dokumen berasal dari lebih dari satu Company."));
		}

		// ── Ambil akun AR dan customer dari SI (source of truth) ───────
		if (payable_si.length === 0) {
			frappe.throw(__("Tidak ada Sales Invoice dengan outstanding > 0, tidak bisa menentukan akun AR dan customer."));
		}
		const receivable_account = payable_si[0].debit_to;
		const customer           = payable_si[0].customer;

		// ── Hitung total & build references ───────────────────────────
		const total_si = payable_si.reduce((sum, si) => sum + flt(si.outstanding_amount), 0);
		const total_je = payable_je.reduce((sum, je) => sum + flt(je.total_debit), 0);
		const total_outstanding = total_si + total_je;

		const ref_si = payable_si.map(si => ({
			reference_doctype:  "Sales Invoice",
			reference_name:     si.name,
			bill_no:            si.bill_no || "",
			due_date:           si.due_date,
			total_amount:       flt(si.grand_total),
			outstanding_amount: flt(si.outstanding_amount),
			allocated_amount:   flt(si.outstanding_amount),
		}));

		const ref_je = payable_je.map(je => ({
			reference_doctype:  "Journal Entry",
			reference_name:     je.name,
			total_amount:       flt(je.total_debit),
			outstanding_amount: flt(je.total_debit),
			allocated_amount:   flt(je.total_debit),
		}));

		const references = [...ref_si, ...ref_je];
		const total_docs = payable_si.length + payable_je.length;

		frappe.confirm(
			__(`Akan membuat Payment Entry untuk <b>${total_docs}</b> tagihan ` +
			   `(${payable_si.length} SI + ${payable_je.length} JE)<br>` +
			   `Total Outstanding: <b>${format_currency(total_outstanding, frm.doc.currency || "IDR")}</b><br>` +
			   `Lanjutkan?`),
			async () => {
				try {
					const pe = await frappe.db.insert({
						doctype:         "Payment Entry",
						payment_type:    "Receive",
						posting_date:    frm.doc.date || frappe.datetime.get_today(),
						company:         frm.doc.company,
						unit:            frm.doc.unit,
						party_type:      "Customer",
						party:           customer,
						paid_to:         bank_account,
						paid_amount:     total_outstanding,
						received_amount: total_outstanding,
						party_account:   receivable_account,
						references:      references,
						nota_piutang_pemenuhan_kontrak: frm.doc.name,
					});

					frappe.show_alert({
						message: __(`Payment Entry <b>${pe.name}</b> berhasil dibuat.`),
						indicator: "green"
					}, 5);
					frappe.set_route("Form", "Payment Entry", pe.name);

				} catch (err) {
					frappe.msgprint({
						title: __("Gagal Membuat Payment Entry"),
						message: err.message || JSON.stringify(err),
						indicator: "red"
					});
				}
			}
		);

	} catch (err) {
		frappe.msgprint({
			title: __("Error"),
			message: err.message || JSON.stringify(err),
			indicator: "red"
		});
	}
}