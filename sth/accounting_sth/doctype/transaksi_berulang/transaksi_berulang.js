// Client Script: Transaksi Berulang
// Module: Accounting STH

frappe.ui.form.on('Transaksi Berulang', {

    // ─── Fetch supplier & premi dari Purchase Invoice ───────────────────────
    refresh: function (frm) {
        set_pi_filter(frm);
        if (frm.doc.docstatus == 1) {
            frm.add_custom_button(__("Lihat GL Entry"), function () {
                frappe.route_options = {
                    voucher_type: frm.doc.doctype,
                    voucher_no: frm.doc.name,
                    company: frm.doc.company,
                };
                frappe.set_route("query-report", "General Ledger");
            });
        }
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
        frm.set_query('ppn_masukan_account', function () {
            return {
                filters: {
                    company: frm.doc.company,
                    is_group: 0
                }
            };
        });
        frm.set_query('biaya_admin_account', function () {
            return {
                filters: {
                    company: frm.doc.company,
                    is_group: 0
                }
            };
        });
        frm.set_query('biaya_asuransi_account', function () {
            return {
                filters: {
                    company: frm.doc.company,
                    is_group: 0
                }
            };
        });
    },

    validate:function(frm){
        if(frm.doc.jenis_transaksi == "LEASING"){
            hitung_total_pembayaran_pertama(frm)
            hitung_nilai_pelunasan(frm)    
        }
    },

    jenis_transaksi: function (frm) {
        frm.set_value('tarik_purchase_invoice', '');
        set_pi_filter(frm);
        isi_jurnal_sewa(frm);
    },

    jenis_pertanggungan: function(frm){
        isi_jurnal_sewa(frm)
    },

    before_save: function(frm) {
        return validate_duplicate_purchase_invoice(frm);
    },
    
    tarik_purchase_invoice: function (frm) {
        validate_duplicate_purchase_invoice(frm);
        if (!frm.doc.tarik_purchase_invoice) {
            frm.set_value('nama_vendor', '');
            frm.set_value('premi', 0);
            frm.set_value('jurnal_debit', '');
            return;
        }

        frappe.db.get_doc('Purchase Invoice', frm.doc.tarik_purchase_invoice)
            .then(pi => {
                // supplier → nama_vendor
                

                // total (bukan grand_total) → premi
                if (frm.doc.jenis_transaksi == "ASURANSI") {
                    frm.set_value('nama_vendor', pi.supplier);
                    frm.set_value('tanggal_mulai', pi.posting_date);
                    frm.set_value('periode_from', pi.posting_date);
                    frm.set_value('premi', pi.items[0].amount);
                    frm.set_value('jurnal_kredit', pi.items[0].expense_account);
                }
                else if (frm.doc.jenis_transaksi == "SEWA") { 
                    frm.set_value('nama_vendor', pi.supplier);
                    frm.set_value('tanggal_mulai', pi.posting_date);
                    frm.set_value('periode_from', pi.posting_date);
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
                else if (frm.doc.jenis_transaksi == "LEASING"){
                    frm.set_value('vendor', pi.supplier)
                    frm.set_value('po', pi.bill_no)

                    let item = pi.items[0];
                    if (item) {
                        let qty1_amount = item.rate; // 1 qty → pakai rate (harga satuan)
                        let ppn = qty1_amount * 0.11;
                        let pbbkb = frm.doc.pbbkb || 0;

                        frm.set_value('dpp', qty1_amount);
                        frm.set_value('ppn', ppn);
                        frm.set_value('pbbkb', pbbkb);
                        frm.set_value('total', qty1_amount + ppn);
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
        isi_jurnal_sewa(frm);
    },

    // ─── Hitung otomatis tanggal_mulai dari periode_from ─────────────────────
    // tanggal_mulai mengambil hari dari tanggal_mulai yang sudah ada,
    // lalu update bulan/tahunnya ke periode_from
    periode_from: function (frm) {
        // _update_tanggal_mulai(frm);
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
    },
    pembayaran_uang_muka: function(frm){
        hitung_total_pembayaran_pertama(frm)
        hitung_nilai_pelunasan(frm)
        generate_leasing_schedule(frm)
    },
    pembayaran_angsuran_pertama: function(frm){
        hitung_total_pembayaran_pertama(frm)
        hitung_nilai_pelunasan(frm)
        generate_leasing_schedule(frm)
    },
    biaya_admin: function(frm){
        hitung_total_pembayaran_pertama(frm)
        hitung_nilai_pelunasan(frm)
        generate_leasing_schedule(frm)
    },
    admin_polis: function(frm){
        hitung_total_pembayaran_pertama(frm)
        hitung_nilai_pelunasan(frm)
        generate_leasing_schedule(frm)
    },
    jumlah_angsuran:function(frm) {
        hitung_pembayaran_angsuran_perbulan(frm)
    },
    nilai_pelunasan:function(frm){
        hitung_pembayaran_angsuran_perbulan(frm)
    },
    asuransi_kredit: function(frm){
        hitung_pembayaran_angsuran_perbulan(frm)
    },
    nilai_bunga: function(frm){
        hitung_pembayaran_angsuran_perbulan(frm)
    },
    tanggal_efektif: function(frm){
        generate_leasing_schedule(frm)
    },

});

frappe.ui.form.on("Transaksi Berulang Leasing Table", {
    bunga: function(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        recalculate_saldo_from(frm, row.idx);
    },
    angsuran: function(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        recalculate_saldo_from(frm, row.idx);
    },
});


function hitung_total_pembayaran_pertama(frm){
    frm.set_value("total_pembayaran_pertama", frm.doc.pembayaran_uang_muka + frm.doc.pembayaran_angsuran_pertama + frm.doc.biaya_admin + frm.doc.admin_polis)
    frm.refresh_fields()
}

function hitung_nilai_pelunasan(frm){
    frm.set_value("nilai_pelunasan", frm.doc.total - frm.doc.pembayaran_uang_muka)
    frm.refresh_fields()
}

function hitung_pembayaran_angsuran_perbulan(frm){
    const total_kredit = flt(frm.doc.nilai_pelunasan)
                       + flt(frm.doc.asuransi_kredit)
                       + flt(frm.doc.nilai_bunga);

    frm.doc.total_kredit                 = total_kredit;
    frm.doc.pembayaran_angsuran_perbulan = total_kredit / parseInt(frm.doc.jumlah_angsuran || 1);
    frm.refresh_fields(["total_kredit", "pembayaran_angsuran_perbulan"]);

    generate_leasing_schedule(frm);
}

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

async function set_pi_filter(frm) {
    const map = {
        'ASURANSI': 'Asuransi',
        'SEWA': 'Sewa',
        'LEASING': 'Leasing'
    };

    const is_leasing = frm.doc.jenis_transaksi === 'LEASING';

    // Ambil semua PI yang sudah dipakai di Transaksi Berulang lain
    const results = await frappe.db.get_list('Transaksi Berulang', {
        filters: [
            ['name', '!=', frm.doc.name || ''],
            ['docstatus', '!=', 2]
        ],
        fields: ['tarik_purchase_invoice'],
        limit: 0
    });

    const used_pi_raw = results
        .map(r => r.tarik_purchase_invoice)
        .filter(Boolean);

    let used_pi = [];

    if (is_leasing) {
        // Hitung berapa kali tiap PI dipakai
        const pi_count = {};
        for (const pi of used_pi_raw) {
            pi_count[pi] = (pi_count[pi] || 0) + 1;
        }

        // Hanya exclude PI yang hitungannya sudah >= qty-nya
        const unique_pis = Object.keys(pi_count);
        await Promise.all(unique_pis.map(async (pi) => {
            const pi_doc = await frappe.db.get_doc('Purchase Invoice', pi);
            const max_qty = (pi_doc.items || []).reduce((sum, item) => sum + (item.qty || 0), 0);
            if (pi_count[pi] >= max_qty) {
                used_pi.push(pi);
            }
        }));

    } else {
        // Non-Leasing: exclude semua PI yang sudah pernah dipakai
        used_pi = [...new Set(used_pi_raw)];
    }

    frm.set_query('tarik_purchase_invoice', function () {
        return {
            filters: {
...(frm.doc.nama_vendor && { supplier: frm.doc.nama_vendor }),
                ...(used_pi.length && { name: ['not in', used_pi] })
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

    } else if (frm.doc.jenis_transaksi === 'ASURANSI') {
        const mapping_pertanggungan = {
            'JASA ASURANSI ALAT BERAT':      '8212601',
            'JASA ASURANSI GEDUNG/PROPERTI': '8212601',
            'JASA ASURANSI KENDARAAN':       '8212601',
            'JASA ASURANSI KESEHATAN':       '8212603',
            'JASA ASURANSI MESIN PABRIK':    '8212603',
            'JASA ASURANSI UMUM':            '8212603',
        };

        const pertanggungan = frm.doc.jenis_pertanggungan;
        const account_number = mapping_pertanggungan[pertanggungan];

        if (!pertanggungan) {
            frappe.msgprint({
                title: __('Jenis Pertanggungan Kosong'),
                message: __('Harap isi Jenis Pertanggungan terlebih dahulu.'),
                indicator: 'orange'
            });
            return;
        }

        if (!account_number) {
            frappe.msgprint({
                title: __('Mapping Tidak Ditemukan'),
                message: __('Jenis Pertanggungan "{0}" tidak dikenali. Periksa konfigurasi mapping akun.', [pertanggungan]),
                indicator: 'red'
            });
            return;
        }

        frappe.db.get_value(
            'Account',
            { account_number: account_number, company: frm.doc.company },
            'name',
            function (r) {
                if (r && r.name) {
                    frm.set_value('jurnal_debit', r.name);
                    frappe.show_alert({
                        message: __('Akun kredit otomatis diisi: {0}', [r.name]),
                        indicator: 'green'
                    }, 4);
                } else {
                    frappe.msgprint({
                        title: __('Akun Tidak Ditemukan'),
                        message: __('Tidak ada akun dengan nomor {0} untuk perusahaan ini. Periksa master Chart of Accounts.', [account_number]),
                        indicator: 'red'
                    });
                }
            }
        );
    } else if (frm.doc.jenis_transaksi === 'LEASING') {

        if(frm.doc.tarik_purchase_invoice){
            // 1. leasing_jurnal_debit → ambil dari Purchase Invoice → Supplier → hutang_leasing_procurement_settings
            frappe.db.get_value(
                'Purchase Invoice',
                { name: frm.doc.tarik_purchase_invoice },
                'supplier',
                function (r) {
                    if (!r || !r.supplier) {
                        frappe.msgprint({
                            title: __('Supplier Tidak Ditemukan'),
                            message: __('Purchase Invoice tidak memiliki supplier.'),
                            indicator: 'red'
                        });
                        return;
                    }

                    // 1. leasing_jurnal_debit → Purchase Invoice → Supplier → child table hutang_leasing_procurement_settings
                    frappe.db.get_value(
                        'Purchase Invoice',
                        { name: frm.doc.tarik_purchase_invoice },
                        'supplier',
                        function (r) {
                            if (!r || !r.supplier) {
                                frappe.msgprint({
                                    title: __('Supplier Tidak Ditemukan'),
                                    message: __('Purchase Invoice tidak memiliki supplier.'),
                                    indicator: 'red'
                                });
                                return;
                            }

                            // Query langsung ke child table, filter parent=supplier & company
                            frappe.db.get_list(
                                'Hutang Leasing Procurement Settings',  // nama child doctype
                                {
                                    filters: {
                                        parent: r.supplier,
                                        parenttype: 'Supplier',
                                        company: frm.doc.company
                                    },
                                    fields: ['account'],
                                    limit: 1
                                },
                                function (rows) {
                                    if (rows && rows.length > 0 && rows[0].account) {
                                        frm.set_value('leasing_jurnal_debit', rows[0].account);
                                    } else {
                                        frappe.msgprint({
                                            title: __('Akun Tidak Ditemukan'),
                                            message: __('Tidak ada akun untuk company ' + frm.doc.company + ' di tabel Hutang Leasing Procurement Settings supplier ini.'),
                                            indicator: 'red'
                                        });
                                    }
                                }
                            );
                        }
                    );
                }
            );

            // 2. biaya_bunga_leasing_debit → akun 9210102
            frappe.db.get_value(
                'Account',
                { account_number: '9210102', company: frm.doc.company },
                'name',
                function (r) {
                    if (r && r.name) {
                        frm.set_value('biaya_bunga_leasing_debit', r.name);
                    } else {
                        frappe.msgprint({
                            title: __('Akun Tidak Ditemukan'),
                            message: __('Tidak ada akun dengan nomor 9210102. Periksa master Chart of Accounts.'),
                            indicator: 'red'
                        });
                    }
                }
            );

            // 3. jurnal_kredit → bank_account dari Unit via tarik_purchase_invoice
            if (!frm.doc.tarik_purchase_invoice) {
                frappe.msgprint({
                    title: __('Purchase Invoice Kosong'),
                    message: __('Harap isi field Purchase Invoice terlebih dahulu.'),
                    indicator: 'orange'
                });
            } else {
                frappe.db.get_value(
                    'Purchase Invoice',
                    frm.doc.tarik_purchase_invoice,
                    'unit',
                    function (pinv) {
                        if (!pinv || !pinv.unit) {
                            frappe.msgprint({
                                title: __('Unit Tidak Ditemukan'),
                                message: __('Purchase Invoice tidak memiliki Unit. Periksa data PINV.'),
                                indicator: 'red'
                            });
                            return;
                        }

                        frappe.db.get_value(
                            'Unit',
                            pinv.unit,
                            'bank_account',
                            function (unit) {
                                if (!unit || !unit.bank_account) {
                                    frappe.msgprint({
                                        title: __('Bank Account Tidak Ditemukan'),
                                        message: __('Unit "{0}" tidak memiliki Bank Account. Periksa master Unit.', [pinv.unit]),
                                        indicator: 'red'
                                    });
                                    return;
                                }

                                frm.set_value('jurnal_kredit', unit.bank_account);
                                frappe.show_alert({
                                    message: __('Akun kredit otomatis diisi: {0}', [unit.bank_account]),
                                    indicator: 'green'
                                }, 4);
                            }
                        );
                    }
                );
            }

            // 4. Popup pilih akun → leasing_jurnal_kredit + jurnal_debit (2212001 atau 2141101)
            frappe.db.get_list('Account', {
                filters: {
                    account_number: ['in', ['2212001', '2141101']],
                    company: frm.doc.company
                },
                fields: ['name', 'account_number', 'account_name'],
                limit: 2
            }).then(function (accounts) {
                if (!accounts || accounts.length === 0) {
                    frappe.msgprint({
                        title: __('Akun Tidak Ditemukan'),
                        message: __('Tidak ada akun 2212001 atau 2141101. Periksa master Chart of Accounts.'),
                        indicator: 'red'
                    });
                    return;
                }

                const options = accounts.map(a => ({
                    label: `${a.account_number} - ${a.account_name || a.name}`,
                    value: a.name
                }));

                frappe.prompt(
                    [
                        {
                            fieldname: 'selected_account',
                            label: __('Pilih Akun Hutang Leasing'),
                            fieldtype: 'Select',
                            options: options.map(o => o.label).join('\n'),
                            reqd: 1,
                            description: __('Akun ini akan diisi ke Leasing Jurnal Kredit dan Jurnal Debit')
                        }
                    ],
                    function (values) {
                        const selected = options.find(o => o.label === values.selected_account);
                        if (!selected) return;

                        frm.set_value('leasing_jurnal_kredit', selected.value);
                        frm.set_value('jurnal_debit', selected.value);

                        frappe.show_alert({
                            message: __('Akun hutang leasing otomatis diisi: {0}', [selected.value]),
                            indicator: 'green'
                        }, 4);
                    },
                    __('Pilih Akun Hutang Leasing'),
                    __('Konfirmasi')
                );
            });
        }

        }

        
}


async function validate_duplicate_purchase_invoice(frm) {
    const invoice = frm.doc.tarik_purchase_invoice;
    if (!invoice) return;

   

    // Ambil semua dokumen Transaksi Berulang yang pakai PI yang sama
    const existing_docs = await frappe.db.get_list('Transaksi Berulang', {
        filters: [
            ['tarik_purchase_invoice', '=', invoice],
            ['name', '!=', frm.doc.name],
            ['docstatus', '!=', 2]
        ],
        fields: ['name'],
        limit: 0   // ambil semua, bukan hanya 1
    });

    const existing_count = (existing_docs || []).length;
    const pi_doc = await frappe.db.get_doc('Purchase Invoice', invoice);
    const is_leasing = frm.doc.jenis_transaksi == 'LEASING' || pi_doc.invoice_type == "Leasing" ;

    if (is_leasing) {
        // Untuk Leasing: maksimal dokumen = total qty di Purchase Invoice
        
        const max_allowed = (pi_doc.items || []).reduce((sum, item) => sum + (item.qty || 0), 0);
        if (existing_count >= max_allowed) {
            reset_and_notify(frm, invoice, __( 
                'Purchase Invoice <strong>{0}</strong> sudah digunakan di <strong>{1}</strong> Transaksi Berulang. ' +
                'Batas maksimal untuk Leasing adalah <strong>{2}</strong> dokumen (sesuai qty di Purchase Invoice).',
                [invoice, existing_count, max_allowed]
            ));
        }

    } else {
        // Non-Leasing: tetap hanya boleh 1 dokumen per PI
        if (existing_count > 0) {
            reset_and_notify(frm, invoice, __(
                'Purchase Invoice <strong>{0}</strong> sudah digunakan di dokumen <strong>{1}</strong>. ' +
                'Tidak boleh dipakai di lebih dari satu Transaksi Berulang.',
                [invoice, existing_docs[0].name]
            ));
        }
    }
}

function reset_and_notify(frm, invoice, message) {
    frappe.model.set_value(frm.doc.doctype, frm.doc.name, 'tarik_purchase_invoice', '');
    frappe.msgprint({
        title: __('Duplikat Purchase Invoice'),
        indicator: 'red',
        message: message
    });
    frappe.validated = false;
}

// ─── Helper ──────────────────────────────────────────────────
function generate_leasing_schedule(frm) {
    if (!frm.doc.tanggal_efektif || !frm.doc.jumlah_angsuran || !frm.doc.pembayaran_angsuran_perbulan) return;
    frm.clear_table("transaksi_berulang_leasing_table");

    const jumlah   = parseInt(frm.doc.jumlah_angsuran);
    const angsuran = flt(frm.doc.pembayaran_angsuran_perbulan);
    const dp       = flt(frm.doc.pembayaran_uang_muka);
    let   saldo    = flt(frm.doc.total) + flt(frm.doc.nilai_bunga) + flt(frm.doc.asuransi_kredit);

    // Baris pertama: Down Payment
    saldo -= dp;
    frm.add_child("transaksi_berulang_leasing_table", {
        tanggal_angsuran    : frm.doc.tanggal_efektif,
        no_transfer         : "Transfer",
        tenor               : 0,
        angsuran            : dp,
        bunga               : 0,
        pembayaran_pokok    : dp,
        denda_keterlambatan : 0,
        saldo               : saldo,
        status_dibayar      : "Belum Dibayar"
    });

    // Baris angsuran bulanan
    for (let i = 0; i < jumlah; i++) {
        const tgl              = frappe.datetime.add_months(frm.doc.tanggal_efektif, i + 1);
        const bunga            = 0;
        const pembayaran_pokok = angsuran + bunga;
        saldo                 -= pembayaran_pokok;

        frm.add_child("transaksi_berulang_leasing_table", {
            tanggal_angsuran    : tgl,
            no_transfer         : "Transfer",
            tenor               : i + 1,
            angsuran            : angsuran,
            bunga               : bunga,
            pembayaran_pokok    : pembayaran_pokok,
            denda_keterlambatan : 0,
            saldo               : saldo,
            status_dibayar      : "Belum Dibayar"
        });
    }

    frm.refresh_field("transaksi_berulang_leasing_table");
}

function recalculate_saldo_from(frm, from_idx) {
    // from_idx adalah idx (1-based) baris yang diubah
    const rows = frm.doc.transaksi_berulang_leasing_table || [];

    // Saldo acuan baris sebelum from_idx
    let prev_saldo;
    if (from_idx === 1) {
        prev_saldo = flt(frm.doc.total_kredit);
    } else {
        const prev = rows.find(r => r.idx === from_idx - 1);
        prev_saldo = flt(prev ? prev.saldo : frm.doc.total_kredit);
    }

    // Update baris dari from_idx ke bawah
    rows
        .filter(r => r.idx >= from_idx)
        .sort((a, b) => a.idx - b.idx)
        .forEach(r => {
            const pp    = flt(r.angsuran) + flt(r.bunga);
            const saldo = prev_saldo - pp;

            frappe.model.set_value(r.doctype, r.name, "pembayaran_pokok", pp);
            frappe.model.set_value(r.doctype, r.name, "saldo", saldo);

            prev_saldo = saldo;
        });

    frm.refresh_field("transaksi_berulang_leasing_table");
}

