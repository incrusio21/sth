frappe.ui.form.on('Monthly CPO Movement', {
	tanggal_akhir_bulan: function(frm) {
		if (frm.doc.tanggal_akhir_bulan) {
			let date = new Date(frm.doc.tanggal_akhir_bulan);
			let last_day = new Date(date.getFullYear(), date.getMonth() + 1, 0);
			let formatted = frappe.datetime.obj_to_str(last_day);
			
			if (frm.doc.tanggal_akhir_bulan !== formatted) {
				frm.set_value('tanggal_akhir_bulan', formatted);
			} else {
				fetch_cpo_data(frm);
			}
		}
	},

	master_barang: function(frm) { fetch_cpo_data(frm); },
	warehouse: function(frm) { fetch_cpo_data(frm); },
	cost_per_unit_processed: function(frm) { fetch_cpo_data(frm); },
	company: function(frm) {
		frm.set_query('warehouse', function() {
			return {
				filters: {
					company: frm.doc.company,
					is_group: 0
				}
			};
		});
		frm.set_query('akun_cogs', function() {
			return {
				filters: {
					company: frm.doc.company,
					is_group: 0
				}
			};
		});
		fetch_cpo_data(frm);
	},
	onload: function(frm) {
		frm.set_query('warehouse', function() {
			return {
				filters: {
					company: frm.doc.company,
					is_group: 0
				}
			};
		});
		frm.set_query('akun_cogs', function() {
			return {
				filters: {
					company: frm.doc.company,
					is_group: 0
				}
			};
		});
	}
});

function fetch_cpo_data(frm) {
	if (!frm.doc.tanggal_akhir_bulan || !frm.doc.master_barang || !frm.doc.warehouse) return;

	frappe.call({
		method: 'sth.accounting_sth.doctype.monthly_cpo_movement.monthly_cpo_movement.get_cpo_movement_data',
		args: {
			item_code: frm.doc.master_barang,
			warehouse: frm.doc.warehouse,
			tanggal_akhir_bulan: frm.doc.tanggal_akhir_bulan,
			cost_per_unit_produced: frm.doc.cost_per_unit_produced
		},
		callback: function(r) {
            if (!r.message) return;
            let d = r.message;
            frm.set_value('qty_akhir_bulan_lalu',     d.qty_akhir_bulan_lalu);
            frm.set_value('balance_akhir_bulan_lalu', d.balance_akhir_bulan_lalu);
            frm.set_value('total_qty_masuk',          d.total_qty_masuk);
            frm.set_value('total_value_masuk',        d.total_value_masuk);
            frm.set_value('cost_per_unit_sold',       d.cost_per_unit_sold);
            frm.set_value('total_qty_keluar',         d.total_qty_keluar);
            frm.set_value('total_value_keluar',       d.total_value_keluar);
            frm.set_value('qty_stock',        		  d.qty_stock);
            frm.set_value('balance_stock',            d.balance_stock);
            frm.set_value('balance_stock_setelah_cost_per_unit', d.balance_stock_setelah_cost_per_unit);
            frm.set_value('perbedaan',            	  d.perbedaan);
        }
	});
}