frappe.ui.form.on('CIT', {
    onload(frm) {
        update_filter_coa(frm);
    },
    company(frm) {
        frm.trigger('fetch_profit_loss');
        update_filter_coa(frm);
    },

    akhir_tahun_berapa(frm) {
        frm.trigger('fetch_profit_loss');
    },

    kompensasi_kerugian_fiskal(frm) {
        hitung_penghasilan_kena_pajak(frm);
    },

    fetch_profit_loss(frm) {
        const { company, akhir_tahun_berapa } = frm.doc;
        if (!company || !akhir_tahun_berapa) return;

        // 1. Ambil Profit for the Year dari P&L
        const p1 = frappe.call({
            method: 'sth.accounting_sth.doctype.cit.cit.get_profit_for_year',
            args: { company, tahun: akhir_tahun_berapa },
        }).then(r => {
            if (r.exc) return;
            frm.set_value('penghasilan_neto_komersial', r.message || 0);
        });

        // 2. Ambil Report Komersial dan Fiskal
        const p2 = frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Report Komersial dan Fiskal',
                filters: [
                    ['company', '=', company],
                    ['tahun_cek_selisih', '=', akhir_tahun_berapa],
                ],
                fields: ['name'],
                limit: 1,
            },
        }).then(r => {
            if (r.exc || !r.message || !r.message.length) return;

            const docname = r.message[0].name;

            return frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Report Komersial dan Fiskal',
                    name: docname,
                },
            }).then(r2 => {
                if (r2.exc || !r2.message) return;

                const rows = r2.message.report_komersial_dan_fiskal_selisih_table || [];

                let positif = 0;
                let negatif = 0;

                rows.forEach(row => {
                    const val = flt(row.selisih_penyusutan);
                    if (val > 0) {
                        positif += val;
                    } else if (val < 0) {
                        negatif += (val * -1); // simpan sebagai positif
                    }
                });

                frm.set_value('selisih_penyusutan_komersial_vs_fiskal_positif', positif);
                frm.set_value('selisih_penyusutan_komersial_vs_fiskal_negatif', negatif);
            });
        });

        // Tunggu keduanya selesai lalu hitung semua
        Promise.all([p1, p2]).then(() => {
            hitung_jumlah_koreksi(frm);
        });
    },
    persentase_pph_terutang(frm) {
        hitung_pph_terutang(frm);
    },

    pembulatan_penghasilan_kena_pajak(frm) {
        hitung_pph_terutang(frm);
    },
});

// =============================================
// TABEL PENYESUAIAN FISKAL POSITIF
// =============================================
frappe.ui.form.on('Penyesuaian Fiskal Positif', {
    coa(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.coa) return;

        const { company, akhir_tahun_berapa } = frm.doc;
        if (!company || !akhir_tahun_berapa) {
            frappe.msgprint(__('Harap isi Company dan Tahun Fiskal terlebih dahulu.'));
            return;
        }

        frappe.call({
            method: 'frappe.client.get',
            args: { doctype: 'Fiscal Year', name: akhir_tahun_berapa },
        }).then(r => {
            if (r.exc || !r.message) return;
            const yearEnd = r.message.year_end_date;

            frappe.call({
                method: 'sth.accounting_sth.doctype.cit.cit.get_account_balance',
                args: {
                    company: company,
                    account: row.coa,
                    year_end: yearEnd,
                },
            }).then(res => {
                if (res.exc) return;
                frappe.model.set_value(cdt, cdn, 'nilai', Math.abs(flt(res.message)));
            });
        });
    },

    nilai(frm) {
        hitung_jumlah_koreksi(frm);
    },
    penyesuaian_fiskal_positif_remove(frm) {
        hitung_jumlah_koreksi(frm);
    },
});



// =============================================
// TABEL PENYESUAIAN FISKAL NEGATIF
// =============================================
frappe.ui.form.on('Penyesuaian Fiskal Negatif', {
    coa(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.coa) return;

        const { company, akhir_tahun_berapa } = frm.doc;
        if (!company || !akhir_tahun_berapa) {
            frappe.msgprint(__('Harap isi Company dan Tahun Fiskal terlebih dahulu.'));
            return;
        }

        frappe.call({
            method: 'frappe.client.get',
            args: { doctype: 'Fiscal Year', name: akhir_tahun_berapa },
        }).then(r => {
            if (r.exc || !r.message) return;
            const yearEnd = r.message.year_end_date;

            frappe.call({
                method: 'sth.accounting_sth.doctype.cit.cit.get_account_balance',
                args: {
                    company: company,
                    account: row.coa,
                    year_end: yearEnd,
                },
            }).then(res => {
                if (res.exc) return;
                frappe.model.set_value(cdt, cdn, 'nilai', Math.abs(flt(res.message)));
            });
        });
    },

    nilai(frm) {
        hitung_jumlah_koreksi(frm);
    },
    penyesuaian_fiskal_negatif_remove(frm) {
        hitung_jumlah_koreksi(frm);
    },
});

// =============================================
// HELPER FUNCTIONS
// =============================================

function hitung_jumlah_koreksi(frm) {
    // Jumlah dari tabel manual
    let total_positif = 0;
    (frm.doc.penyesuaian_fiskal_positif || []).forEach(row => {
        total_positif += flt(row.nilai);
    });

    let total_negatif = 0;
    (frm.doc.penyesuaian_fiskal_negatif || []).forEach(row => {
        total_negatif += flt(row.nilai);
    });

    // Tambah dari selisih penyusutan
    total_positif += flt(frm.doc.selisih_penyusutan_komersial_vs_fiskal_positif);
    total_negatif += flt(frm.doc.selisih_penyusutan_komersial_vs_fiskal_negatif);

    frm.set_value('jumlah_koreksi_positif', total_positif);
    frm.set_value('jumlah_koreksi_negatif', total_negatif);

    // Koreksi fiskal = positif - negatif
    const jumlah_koreksi_fiskal = total_positif - total_negatif;
    frm.set_value('jumlah_koreksi_fiskal', jumlah_koreksi_fiskal);

    // Penghasilan neto fiskal = komersial - koreksi fiskal
    const penghasilan_neto_fiskal =
        flt(frm.doc.penghasilan_neto_komersial) - jumlah_koreksi_fiskal;
    frm.set_value('penghasilan_neto_fiskal', penghasilan_neto_fiskal);

    hitung_penghasilan_kena_pajak(frm);
}

function hitung_penghasilan_kena_pajak(frm) {
    const neto_fiskal = flt(frm.doc.penghasilan_neto_fiskal);
    const kompensasi = flt(frm.doc.kompensasi_kerugian_fiskal);

    const pkp_raw = neto_fiskal - kompensasi;
    const pkp_bulat = Math.ceil(pkp_raw / 1000) * 1000;

    frm.set_value('penghasilan_kena_pajak', pkp_raw);
    frm.set_value('pembulatan_penghasilan_kena_pajak', pkp_bulat);

    // Lanjut hitung PPh terutang
    hitung_pph_terutang(frm);
}

function hitung_pph_terutang(frm) {
    const pkp = flt(frm.doc.pembulatan_penghasilan_kena_pajak);
    const persentase = flt(frm.doc.persentase_pph_terutang) || 22;

    const pph_terutang = pkp * persentase / 100;
    frm.set_value('pph_terutang', pph_terutang);

    hitung_kredit_pajak(frm);
}

function hitung_kredit_pajak(frm) {
    const { company, akhir_tahun_berapa } = frm.doc;
    if (!company || !akhir_tahun_berapa) return;

    // Ambil tahun dari fiscal year → cari year_end_date untuk tahu tahunnya
    frappe.call({
        method: 'frappe.client.get',
        args: {
            doctype: 'Fiscal Year',
            name: akhir_tahun_berapa,
        },
    }).then(r => {
        if (r.exc || !r.message) return;

        const tahun = new Date(r.message.year_end_date).getFullYear();
        const dari = `${tahun}-01-01`;
        const sampai = `${tahun}-12-31`;

        // Ambil PPh 22 (account 1171001) dan PPh 23 (account 1171002) secara paralel
        const q22 = frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'GL Entry',
                filters: [
                    ['company', '=', company],
                    ['account', 'like', '1171001%'],
                    ['posting_date', '>=', dari],
                    ['posting_date', '<=', sampai],
                    ['is_cancelled', '=', 0],
                ],
                fields: ['debit', 'credit'],
                limit: 0,
            },
        });

        const q23 = frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'GL Entry',
                filters: [
                    ['company', '=', company],
                    ['account', 'like', '1171002%'],
                    ['posting_date', '>=', dari],
                    ['posting_date', '<=', sampai],
                    ['is_cancelled', '=', 0],
                ],
                fields: ['debit', 'credit'],
                limit: 0,
            },
        });

        Promise.all([q22, q23]).then(([res22, res23]) => {
            // Nilai kredit pajak = debit - credit (asset account, saldo normal debit)
            const pph_22 = (res22.message || []).reduce((sum, row) => {
                return sum + flt(row.debit) - flt(row.credit);
            }, 0);

            const pph_23 = (res23.message || []).reduce((sum, row) => {
                return sum + flt(row.debit) - flt(row.credit);
            }, 0);

            frm.set_value('pajak_penghasilan_pph_22', pph_22);
            frm.set_value('pajak_penghasilan_pph_23', pph_23);

            const jumlah_kredit_pajak = pph_22 + pph_23;
            frm.set_value('jumlah_kredit_pajak', jumlah_kredit_pajak);

            hitung_pph_pasal_29(frm, jumlah_kredit_pajak);
        });
    });
}

function hitung_pph_pasal_29(frm, jumlah_kredit_pajak) {
    const pph_terutang = flt(frm.doc.pph_terutang);
    const pasal_29 = pph_terutang - jumlah_kredit_pajak;

    frm.set_value('pph_pasal_29_terhutang', pasal_29);
    frm.set_value(
        'status_pph_pasal_29_terhutang',
        pasal_29 >= 0 ? 'KURANG BAYAR' : 'LEBIH BAYAR'
    );
}

function update_filter_coa(frm) {
    frm.set_query("coa", "penyesuaian_fiskal_positif", function (doc, cdt, cdn) {
        return {
            filters: {
                company: doc.company
            }
        };
    });
    frm.set_query("coa", "penyesuaian_fiskal_negatif", function (doc, cdt, cdn) {
        return {
            filters: {
                company: doc.company
            }
        };
    });
}