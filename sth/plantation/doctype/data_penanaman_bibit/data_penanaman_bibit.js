// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt


frappe.ui.form.on("Data Penanaman Bibit", {
	setup(frm) {

		frm.set_query("divisi", function() {

			let filters = {};

			if (frm.doc.company) {
				filters.company = frm.doc.company;
			}

			return {
				filters: filters
			};

		});


		frm.set_query("blok", function() {

			let filters = {
			};

			if (frm.doc.divisi) {
				filters.divisi = frm.doc.divisi;
			}

			return {
				filters: filters
			};

		});

	},
	onload: function(frm) {      
		if (frm.is_new() && !frm.doc.posting_time) {
			let now = frappe.datetime.now_time(); 
			frm.set_value("posting_time", now);
		}
	},

	company: function(frm) {
		isi_account_company(frm)
	},

	refresh(frm) {
		frm.set_query("data_penyemaian_bibit", function(doc) {
			return {
				"filters": [
					["company",  "=", doc.company],
					["docstatus",  "=", 1],
				]
			};
		});
		set_batch_filters(frm)
		if(frm.is_new()){
			isi_account_company(frm)
		}
		if(frm.doc.docstatus == 1){
			show_gl_button(frm)
		}
		if (frm.doc.data_penyemaian_bibit && frm._base_rupiah_basis === undefined) {
			fetch_base_rupiah_basis(frm);
		}
	},
	data_penyemaian_bibit: function(frm) {
	    if (!frm.doc.data_penyemaian_bibit) {
	        frm._base_rupiah_basis = 0;
	        frm.set_value('qty', 0);
	        frm.set_value('rupiah_basis', 0);
	        return;
	    }
	    fetch_base_rupiah_basis(frm, (r) => {
	        frm.set_value('qty', r.message.qty);
	        frm.set_value('available_qty', r.message.qty);
	        hitung_total(frm);
	    });
	},
	batch: function(frm) {
		if (!frm.doc.batch) {
            frm.set_value("data_penyemaian_bibit", "");
            return;
        }

        frappe.db.get_value(
            "Data Penyemaian Bibit",
            {
                batch: frm.doc.batch,
                docstatus: 1
            },
            "name"
        ).then(r => {

            if (r.message && r.message.name) {

                frm.set_value(
                    "data_penyemaian_bibit",
                    r.message.name
                );

            } else {

                frm.set_value(
                    "data_penyemaian_bibit",
                    ""
                );

                frappe.msgprint(
                    "Data Penyemaian Bibit untuk batch ini tidak ditemukan."
                );
            }

        });

		if (!frm.doc.batch) {
			frm.set_value('rupiah_basis', 0);
			frm.set_value('total_bkm', 0);
			frm.set_value('total_jurnal', 0);
			return;
		}
		frappe.call({
			method: 'sth.plantation.doctype.data_penanaman_bibit.data_penanaman_bibit.get_rupiah_basis_by_batch',
			args: { batch: frm.doc.batch },
			callback: (r) => {
				if (r.message) {
					frm.set_value('total_bkm', r.message.total_bkm);
					hitung_total(frm);
				}
			}
		});
	},
	qty: function(frm) {
		hitung_total(frm);
	},

	item_code: function(frm){
		set_batch_filters(frm)
	}
});

// function hitung_total(frm) {
// 	var jumlah = frm.doc.qty || 0;
// 	var basis = frm.doc.rupiah_basis || 0;
// 	frm.set_value('total_bibit', jumlah * basis)
// 	frm.set_value('total_jurnal', frm.doc.total_bibit + frm.doc.total_bkm);
// }

function fetch_base_rupiah_basis(frm, then) {
    frappe.call({
        method: 'sth.plantation.doctype.data_penanaman_bibit.data_penanaman_bibit.get_data_penyemaian',
        args: { data_penyemaian_bibit: frm.doc.data_penyemaian_bibit },
        callback: (r) => {
            if (r.message) {
                frm._base_rupiah_basis = flt(r.message.rupiah_basis);
                if (then) then(r);
            }
        }
    });
}

function hitung_total(frm) {
    const qty = flt(frm.doc.qty);
    const basis = flt(frm._base_rupiah_basis);
    const available_qty = flt(frm.doc.available_qty);
    const total_bkm = flt(frm.doc.total_bkm);

    const total_bibit = qty * basis;

    let actual_amount_bkm = 0;
    if (available_qty) {
        actual_amount_bkm = (qty / available_qty) * total_bkm;
    }

    const total_jurnal = total_bibit + actual_amount_bkm;

    frm.set_value('total_bibit', total_bibit);
    frm.set_value('actual_amount_bkm', actual_amount_bkm);
    frm.set_value('total_jurnal', total_jurnal);
    frm.set_value('rupiah_basis', qty ? total_jurnal / qty : 0);
}

function set_batch_filters(frm){
	frm.set_query('batch', () => ({
		filters: { item_code: frm.doc.item_code }
	}));
}

function isi_account_company(frm){
	if (!frm.doc.company) return;
	frappe.call({
		method: 'sth.plantation.doctype.data_penanaman_bibit.data_penanaman_bibit.get_akun_penanaman',
		args: { company: frm.doc.company },
		callback: (r) => {
			if (r.message) {
				if(!frm.doc.debit_account){
					frm.set_value('debit_account', r.message.debit_account);
				}
				if(!frm.doc.credit_account){
					frm.set_value('credit_account', r.message.credit_account);
				}
			}
		}
	});
}

function show_gl_button(frm){
	if(frm.doc.docstatus == 1){
		frm.add_custom_button(__('GL Entry'), () => {
			frappe.route_options = {
				voucher_no: frm.doc.name,
				voucher_type: frm.doc.doctype,
				from_date: frm.doc.posting_date,
				to_date: frm.doc.posting_date,
				company: frm.doc.company
			};
			frappe.set_route('query-report', 'General Ledger');
		}, __('View'));
	}
}