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
		setup_filter(frm)
	},
	company: function(frm) {
		setup_filter(frm)
	},
	no_kontrak: function(frm) {
		if (!frm.doc.no_kontrak) return;

		frappe.db.get_doc('Sales Order', frm.doc.no_kontrak)
			.then(so => {
				frm.set_value('company', so.company);

				if (!so.payment_schedule || so.payment_schedule.length === 0) {				
					return;
				}

				const termin_pertama = so.payment_schedule[0];
				frm.set_value('nilai_dp', termin_pertama.payment_amount);
				
				if (so.unit) {
					frm.set_value('unit', so.unit);
					frappe.db.get_doc('Unit', so.unit)
						.then(unit_doc => {
							if (unit_doc.bank_account) {
								frm.set_value('akun_kas_bank', unit_doc.bank_account);
							}
						})
						.catch(() => {
							frappe.msgprint(__('Unit {0} not found.', [so.unit]));
						});
				}

			})
			.catch(() => {
				frappe.msgprint(__('Sales Order {0} not found.', [frm.doc.no_kontrak]));
			});

		if (frm.doc.tipe === 'Pemenuhan Kontrak') {
			fetch_si_pengiriman(frm);
		}
	},
	tipe: function(frm) {
		if (frm.doc.tipe === 'Pemenuhan Kontrak' && frm.doc.no_kontrak) {
			fetch_si_pengiriman(frm);
		}
	}
});

function setup_filter(frm){
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

function fetch_si_pengiriman(frm) {
	if (!frm.doc.no_kontrak) {
		frappe.msgprint(__('Pilih No. Kontrak terlebih dahulu.'));
		return;
	}

	frappe.call({
		method: 'sth.accounting_sth.doctype.nota_piutang.nota_piutang.get_si_pengiriman',
		args: { no_kontrak: frm.doc.no_kontrak },
		callback: function(r) {
			if (!r.message || r.message.length === 0) {
				frappe.msgprint(__('Tidak ada Sales Invoice Pengiriman untuk kontrak ini.'));
				return;
			}

			frm.clear_table('nota_hutang_pemenuhan_kontrak_table');  
			console.log(r.message)
			r.message.forEach(si => {
				let row = frm.add_child('nota_hutang_pemenuhan_kontrak_table');  
				row.pengakuan_penjualan = si.name;
				row.qty = si.qty;
				row.rate = si.rate;
				row.subtotal = si.subtotal;
				row.posting_date = si.posting_date;
				
			});	

			frm.refresh_field('nota_hutang_pemenuhan_kontrak_table');
			fetch_nilai_kontrak(frm);  
		}
	});
}

function fetch_nilai_kontrak(frm) {
	if (!frm.doc.no_kontrak) return;

	frappe.call({
		method: 'sth.accounting_sth.doctype.nota_piutang.nota_piutang.get_nilai_kontrak',
		args: { no_kontrak: frm.doc.no_kontrak },
		callback: function(r) {
			if (!r.message) return;

			const d = r.message;

			frm.set_value('nilai_kontrak', d.nilai_kontrak);
			frm.set_value('dpp',           d.dpp);
			frm.set_value('ppn',           d.ppn);
			frm.set_value('dp_dpp',        d.dp_dpp);
			frm.set_value('dp_ppn',        d.dp_ppn);

			// sisa_dpp = grand_total dari table - dp_dpp
			const table_total = (frm.doc.nota_hutang_pemenuhan_kontrak_table || [])
				.reduce((sum, row) => sum + (row.subtotal || 0), 0);

			let sisa_dpp = table_total - d.dp_dpp;
			let sisa_ppn = sisa_dpp * d.tax_rate_total;

			if (sisa_dpp < 0){
				sisa_dpp = 0
			}
			if (sisa_ppn < 0){
				sisa_ppn = 0
			}

			frm.set_value('sisa_dpp', sisa_dpp);
			frm.set_value('sisa_ppn', sisa_ppn);
			build_reclass_table(frm, d.tax_rate_total);
		}
	});
}

function build_reclass_table(frm, tax_rate_total) {
	const rows = frm.doc.nota_hutang_pemenuhan_kontrak_table || [];
	if (!rows.length) return;

	// ── 1. Group by bulan-tahun dari posting_date ──────────────────────
	const groups = {};
	rows.forEach(row => {
		if (!row.posting_date) return;
		const d    = frappe.datetime.str_to_obj(row.posting_date);
		const key  = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
		if (!groups[key]) groups[key] = { rows: [], posting_date: row.posting_date };
		groups[key].rows.push(row);
	});

	// ── 2. Konsumsi dp_dpp secara berurutan per grup ───────────────────
	let dp_remaining = frm.doc.dp_dpp || 0;
	const reclass_rows = [];

	Object.keys(groups).sort().forEach(key => {
		const grp          = groups[key];
		const sum_subtotal = grp.rows.reduce((s, r) => s + (r.subtotal || 0), 0);
		const sum_qty      = grp.rows.reduce((s, r) => s + (r.qty     || 0), 0);
		const avg_rate     = grp.rows.reduce((s, r) => s + (r.rate    || 0), 0) / grp.rows.length;

		// Kurangi dp_dpp dari subtotal grup ini
		const consumed     = Math.min(dp_remaining, sum_subtotal);
		dp_remaining      -= consumed;
		const net_subtotal = sum_subtotal - consumed;

		console.log(net_subtotal)

		if (net_subtotal <= 0) return;  // semua tercover DP, skip

		// Proporsi qty setelah dikurangi DP
		const qty_ratio = sum_subtotal > 0 ? net_subtotal / sum_subtotal : 1;
		const net_qty   = sum_qty;

		// Periode: nama bulan + tahun
		const [year, month] = key.split('-');
		const month_name    = frappe.datetime.month_abbr ? 
			moment(grp.posting_date).format('MMMM YYYY') :
			new Date(year, parseInt(month) - 1, 1)
				.toLocaleString('id-ID', { month: 'long', year: 'numeric' });

		const ppn         = net_subtotal * tax_rate_total;
		const grand_total = net_subtotal + ppn;

		reclass_rows.push({
			periode:     month_name,
			qty:         net_qty,
			rate:        avg_rate,
			subtotal:    net_subtotal,
			ppn:         ppn,
			grand_total: grand_total,
		});
	});

	// ── 3. Isi table (clear dulu, tapi preserve reclass & akun_reclass) ─
	const existing = {};
	(frm.doc.reclass_pengakuan_penjualan || []).forEach(r => {
		existing[r.periode] = {
			reclass:      r.reclass,
			akun_reclass: r.akun_reclass,
		};
	});

	frm.clear_table('reclass_pengakuan_penjualan');

	reclass_rows.forEach(data => {
		const row        = frm.add_child('reclass_pengakuan_penjualan');
		row.periode      = data.periode;
		row.qty          = data.qty;
		row.rate         = data.rate;
		row.subtotal     = data.subtotal;
		row.ppn          = data.ppn;
		row.grand_total  = data.grand_total;

		// Preserve nilai reclass & akun_reclass kalau periode sudah ada sebelumnya
		
	});

	frm.refresh_field('reclass_pengakuan_penjualan');
	frm.fields_dict['reclass_pengakuan_penjualan'].grid.cannot_add_rows = true;
	frm.fields_dict['reclass_pengakuan_penjualan'].grid.refresh();
}

async function make_payment_entry(frm) {
    try {
        // 1. Ambil bank_account dari doctype Unit
        if (!frm.doc.unit) {
            frappe.throw(__("Field Unit kosong, tidak bisa mengambil akun bank."));
        }

        const unit_doc = await frappe.db.get_doc("Unit", frm.doc.unit);
        const bank_account = unit_doc.bank_account;

        if (!bank_account) {
            frappe.throw(__("Doctype Unit tidak memiliki field bank_account yang terisi."));
        }

        // 2. Kumpulkan semua nama SI dari kedua table (deduplikasi dulu)
        const si_from_main = (frm.doc.nota_hutang_pemenuhan_kontrak_table || [])
            .filter(row => row.pengakuan_penjualan)
            .map(row => row.pengakuan_penjualan);

        const si_from_reclass = (frm.doc.reclass_pengakuan_penjualan || [])
            .filter(row => row.pengakuan_penjualan_ppn)
            .map(row => row.pengakuan_penjualan_ppn);

        const all_si_names = [...new Set([...si_from_main, ...si_from_reclass])];

        if (all_si_names.length === 0) {
            frappe.throw(__("Tidak ada Sales Invoice di table."));
        }

        // 3. Fetch semua SI untuk mendapatkan outstanding_amount terkini dari Sales Invoice
        const si_docs = await Promise.all(
            all_si_names.map(name => frappe.db.get_doc("Sales Invoice", name))
        );

        // 4. Filter hanya yang outstanding_amount > 0
        const payable_si = si_docs.filter(si => flt(si.outstanding_amount) > 0);

        if (payable_si.length === 0) {
            frappe.throw(__("Semua Sales Invoice sudah lunas (outstanding = 0)."));
        }

        // 5. Validasi: semua SI harus dari company yang sama
        const companies = [...new Set(payable_si.map(d => d.company))];
        if (companies.length > 1) {
            frappe.throw(__("Sales Invoice berasal dari lebih dari satu Company."));
        }

        // 6. Hitung total outstanding
        const total_outstanding = payable_si.reduce(
            (sum, si) => sum + flt(si.outstanding_amount), 0
        );

        // 7. Ambil receivable account dari SI pertama (debit_to)
        const receivable_account = payable_si[0].debit_to;

        // 8. Bangun references array
        const references = payable_si.map(si => ({
            reference_doctype: "Sales Invoice",
            reference_name: si.name,
            bill_no: si.bill_no || "",
            due_date: si.due_date,
            total_amount: flt(si.grand_total),
            outstanding_amount: flt(si.outstanding_amount),
            allocated_amount: flt(si.outstanding_amount),
        }));

        // 9. Dialog konfirmasi
        frappe.confirm(
            __(`Akan membuat Payment Entry untuk <b>${payable_si.length}</b> Sales Invoice<br>
               Total Outstanding: <b>${format_currency(total_outstanding, frm.doc.currency || "IDR")}</b><br>
               Lanjutkan?`),
            async () => {
                try {
                    const pe = await frappe.db.insert({
                        doctype: "Payment Entry",
                        payment_type: "Receive",
                        posting_date: frm.doc.date || frappe.datetime.get_today(),
                        company: frm.doc.company,
                        unit: frm.doc.unit,
                        party_type: "Customer",
                        party: payable_si[0].customer,
                        paid_to: bank_account,
                        paid_amount: total_outstanding,
                        received_amount: total_outstanding,
                        party_account: receivable_account,
                        references: references,
                        nota_piutang_pemenuhan_kontrak: frm.doc.name
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
