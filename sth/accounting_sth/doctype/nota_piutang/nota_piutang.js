frappe.ui.form.on('Nota Piutang', {
	refresh: function(frm) {
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

			r.message.forEach(si => {
				let row = frm.add_child('nota_hutang_pemenuhan_kontrak_table');  
				row.pengakuan_penjualan = si.name;
				row.nominal = si.grand_total;
			});

			frm.refresh_field('nota_hutang_pemenuhan_kontrak_table');  
		}
	});
}