// Client Script: Transaksi Berulang
// Module: Accounting STH

frappe.ui.form.on('Transaksi Berulang', {

    // ─── Fetch supplier & premi dari Purchase Invoice ───────────────────────
    refresh: function (frm) {
        set_pi_filter(frm);
    },

    jenis_transaksi: function (frm) {
        frm.set_value('tarik_purchase_invoice', '');
        set_pi_filter(frm);
        isi_jurnal_sewa(frm);
    },

    tarik_purchase_invoice: function (frm) {
        if (!frm.doc.tarik_purchase_invoice) {
            frm.set_value('nama_vendor', '');
            frm.set_value('premi', 0);
            frm.set_value('jurnal_debit', '');
            return;
        }

        frappe.db.get_doc('Purchase Invoice', frm.doc.tarik_purchase_invoice)
            .then(pi => {
                // supplier → nama_vendor
                frm.set_value('nama_vendor', pi.supplier);
                frm.set_value('tanggal_mulai', pi.posting_date);
                frm.set_value('periode_from', pi.posting_date);

                // total (bukan grand_total) → premi
                if (frm.doc.jenis_transaksi == "ASURANSI") {
                    frm.set_value('premi', pi.items[0].amount);
                    frm.set_value('jurnal_kredit', pi.items[0].expense_account);
                }
                else {
                    // Cari row yang COA-nya mengandung "SEWA DIBAYAR DI MUKA"
                    let sewaRow = pi.non_voucher_match.find(
                        row => row.coa && row.coa.includes('SEWA DIBAYAR DI MUKA')
                    );
                    if (sewaRow) {
                        frm.set_value('premi', sewaRow.dpp);
                    }

                    // Cari row yang COA-nya mengandung "DEPOSIT"
                    let depositRow = pi.non_voucher_match.find(
                        row => row.coa && row.coa.includes('DEPOSIT')
                    );
                    if (depositRow) {
                        console.log
                        frm.set_value('deposit', depositRow.dpp);
                    }
                }

                // Fetch COA dari Non Voucher Match (child table di Purchase Invoice)
                // Filter pakai parent = nama Purchase Invoice
                return frappe.db.get_list('Non Voucher Match', {
                    filters: {
                        parent: frm.doc.tarik_purchase_invoice,
                        parenttype: 'Purchase Invoice'
                    },
                    fields: ['coa'],
                    limit: 1
                });
            })
            .then(rows => {
                if (rows && rows.length && rows[0].coa) {
                    frm.set_value('jurnal_debit', rows[0].coa);
                }
            })
            .catch(err => {
                frappe.msgprint({
                    title: 'Peringatan',
                    indicator: 'orange',
                    message: `Gagal fetch data Purchase Invoice: ${err.message || err}`
                });
            });
    },

    // ─── Refresh: tambah tombol Buat Journal Entry jika sudah submit ─────────
    refresh: function (frm) {
        // if (frm.doc.docstatus === 1) {
        //     frm.add_custom_button(
        //         __('Buat Journal Entry'),
        //         function() {
        //             frappe.confirm(
        //                 `Buat Journal Entry untuk <b>${frm.doc.name}</b>?<br>
        //                 Periode: ${frappe.datetime.str_to_user(frm.doc.periode_from)}
        //                 s/d ${frappe.datetime.str_to_user(frm.doc.periode_to)}<br>
        //                 Masa: ${frm.doc.masa_periode} bulan`,
        //                 function() {
        //                     frappe.call({
        //                         method: 'accounting_sth.accounting_sth.doctype.transaksi_berulang.transaksi_berulang.create_journal_entries',
        //                         args: { docname: frm.doc.name },
        //                         freeze: true,
        //                         freeze_message: __('Membuat Journal Entries...'),
        //                         callback: function(r) {
        //                             if (r.message) {
        //                                 frappe.msgprint({
        //                                     title: 'Berhasil',
        //                                     indicator: 'green',
        //                                     message: r.message
        //                                 });
        //                                 frm.reload_doc();
        //                             }
        //                         }
        //                     });
        //                 }
        //             );
        //         },
        //         __('Aksi')
        //     );
        // }

        frm.set_query('jurnal_debit', function () {
            return {
                filters: {
                    company: frm.doc.company,
                    is_group: 0
                }
            };
        });
        frm.set_query('jurnal_kredit', function () {
            return {
                filters: {
                    company: frm.doc.company,
                    is_group: 0
                }
            };
        });
    },

    // ─── Hitung otomatis tanggal_mulai dari periode_from ─────────────────────
    // tanggal_mulai mengambil hari dari tanggal_mulai yang sudah ada,
    // lalu update bulan/tahunnya ke periode_from
    periode_from: function (frm) {
        _update_tanggal_mulai(frm);
        hitung_bulan(frm);
    },

    periode_to: function (frm) {
        hitung_bulan(frm);
    },

    tanggal_mulai: function (frm) {
        // Cukup validasi saja
        if (frm.doc.periode_from && frm.doc.tanggal_mulai) {
            let periode_from = frappe.datetime.str_to_obj(frm.doc.periode_from);
            let mulai = frappe.datetime.str_to_obj(frm.doc.tanggal_mulai);
            if (mulai < periode_from) {
                frappe.msgprint({
                    title: 'Peringatan',
                    indicator: 'orange',
                    message: 'Tanggal Mulai tidak boleh sebelum Periode From.'
                });
            }
        }
    }
});

// ─── Helper: sinkron tanggal_mulai dengan bulan periode_from ─────────────────
function _update_tanggal_mulai(frm) {
    if (frm.doc.periode_from && frm.doc.tanggal_mulai) {
        // Pertahankan hari dari tanggal_mulai, tapi pakai bulan/tahun dari periode_from
        let pf = frm.doc.periode_from.split('-');   // [yyyy, mm, dd]
        let tm = frm.doc.tanggal_mulai.split('-');  // [yyyy, mm, dd]
        let new_date = `${pf[0]}-${pf[1]}-${tm[2]}`;
        frm.set_value('tanggal_mulai', new_date);
    }
}


function hitung_bulan(frm) {
    let from = frm.doc.periode_from;
    let to = frm.doc.periode_to;

    if (from && to) {
        let date_from = frappe.datetime.str_to_obj(from);
        let date_to = frappe.datetime.str_to_obj(to);

        let bulan = (date_to.getFullYear() - date_from.getFullYear()) * 12
            + (date_to.getMonth() - date_from.getMonth()) + 1;

        if (bulan < 0) {
            frappe.msgprint(__('Periode To tidak boleh lebih kecil dari Periode From'));
            frm.set_value('masa_periode', 0);
            return;
        }

        frm.set_value('masa_periode', bulan);
    }
}

function set_pi_filter(frm) {
    const map = {
        'ASURANSI': 'Asuransi',
        'SEWA': 'Sewa'
    };

    frm.set_query('tarik_purchase_invoice', function () {
        return {
            filters: {
                invoice_type: map[frm.doc.jenis_transaksi] || ''
            }
        };
    });
}

function isi_jurnal_sewa(frm) {
    if (frm.doc.jenis_transaksi === 'SEWA') {
        frappe.db.get_value(
            'Account',
            { account_number: '1181002', company: frm.doc.company },
            'name',
            function (r) {
                if (r && r.name) {
                    frm.set_value('jurnal_kredit', r.name);
                    frappe.show_alert({
                        message: __('Akun kredit otomatis diisi: {0}', [r.name]),
                        indicator: 'green'
                    }, 4);
                } else {
                    frappe.msgprint({
                        title: __('Akun Tidak Ditemukan'),
                        message: __('Tidak ada akun dengan nomor 1181002. Periksa master Chart of Accounts.'),
                        indicator: 'red'
                    });
                }
            }
        );
    }
}