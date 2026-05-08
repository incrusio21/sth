frappe.ui.form.on('Report Komersial dan Fiskal', {
    refresh(frm) {
        set_asset_filter(frm);
        frm.add_custom_button(__('Get All Asset'), () => get_all_asset(frm));
        frm.fields_dict['report_komersial_dan_fiskal_nilai_table'].grid.cannot_add_rows = true;
        frm.fields_dict['report_komersial_dan_fiskal_nilai_table'].grid.refresh();
        frm.fields_dict['report_komersial_dan_fiskal_selisih_table'].grid.cannot_add_rows = true;
        frm.fields_dict['report_komersial_dan_fiskal_selisih_table'].grid.refresh();
    },

    company(frm) {
        set_asset_filter(frm);
        (frm.doc.report_komersial_dan_fiskal_table || []).forEach(row => {
            frappe.model.set_value(row.doctype, row.name, 'asset', '');
        });
        frm.refresh_field('report_komersial_dan_fiskal_table');
    },

    tahun_cek_nilai(frm) {
        let tahun = frm.doc.tahun_cek_nilai;
        if (!tahun) return;
        let sumber = frm.doc.report_komersial_dan_fiskal_table || [];
        if (!sumber.length) {
            frappe.msgprint(__('Tabel utama masih kosong.'));
            return;
        }
        let akhir_tahun = tahun + '-12-31';
        frm.clear_table('report_komersial_dan_fiskal_nilai_table');
        sumber.forEach(src => {
            let nilai_perolehan  = flt(src.nilai_perolehan);
            let ppb_kom          = flt(src.penyusutan_per_bulan_komersial);
            let ppb_fis          = flt(src.penyusutan_per_bulan_fiskal);
            let bulan = src.tanggal_perolehan ? selisih_bulan(src.tanggal_perolehan, akhir_tahun) : 0;
            if (bulan < 0) bulan = 0;
            let row = frm.add_child('report_komersial_dan_fiskal_nilai_table');
            frappe.model.set_value(row.doctype, row.name, {
                asset                          : src.asset,
                penyusutan_per_tahun_komersial : ppb_kom * 12,
                penyusutan_per_tahun_fiskal    : ppb_fis * 12,
                nilai_buku_komersial           : nilai_perolehan - (bulan * ppb_kom),
                nilai_buku_fiskal              : nilai_perolehan - (bulan * ppb_fis),
            });
        });
        frm.refresh_field('report_komersial_dan_fiskal_nilai_table');
    },

    tahun_cek_selisih(frm) {
        let tahun = frm.doc.tahun_cek_selisih;
        if (!tahun) return;
        let sumber = frm.doc.report_komersial_dan_fiskal_table || [];
        if (!sumber.length) {
            frappe.msgprint(__('Tabel utama masih kosong.'));
            return;
        }
        let akhir_tahun = tahun + '-12-31';
        frm.clear_table('report_komersial_dan_fiskal_selisih_table');
        let selisih = 0
        sumber.forEach(src => {
            let ppb_kom = flt(src.penyusutan_per_bulan_komersial);
            let ppb_fis = flt(src.penyusutan_per_bulan_fiskal);
            let masa    = src.tanggal_perolehan ? selisih_bulan(src.tanggal_perolehan, akhir_tahun) : 0;
            if (masa < 0) masa = 0;
            let row = frm.add_child('report_komersial_dan_fiskal_selisih_table');
            frappe.model.set_value(row.doctype, row.name, {
                asset                         : src.asset,
                masa_penyusutan               : masa,
                penyusutan_per_bulan_komersial : ppb_kom * masa,
                penyusutan_per_bulan_fiskal    : ppb_fis * masa,
                selisih_penyusutan            : (ppb_kom * masa) - (ppb_fis * masa),
            });
            selisih += (ppb_kom * masa) - (ppb_fis * masa)
        });
        frm.set_value("total_penyusutan", selisih)
        frm.refresh_field('report_komersial_dan_fiskal_selisih_table');
    },
});

// =============================================
// CHILD TABLE: trigger asset manual (1 per baris)
// =============================================
frappe.ui.form.on('Report Komersial dan Fiskal Table', {
    asset(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.asset) {
            frappe.model.set_value(cdt, cdn, {
                tanggal_perolehan              : null,
                nilai_perolehan                : 0,
                penyusutan_komersial           : 0,
                penyusutan_fiskal              : 0,
                penyusutan_per_bulan_komersial : 0,
                penyusutan_per_bulan_fiskal    : 0,
            });
            // Regenerate tabel turunan juga
            regenerate_tabel_turunan(frm);
            return;
        }
        frappe.call({
            method: 'frappe.client.get',
            args: { doctype: 'Asset', name: row.asset },
            callback(r) {
                if (!r.message) return;
                populate_row_from_asset(cdt, cdn, r.message);

                // ← Setelah row terisi, regenerate kedua tabel
                regenerate_tabel_turunan(frm);
            },
        });
    },
});
// =============================================
// HELPERS
// =============================================

/**
 * Shared: isi field row dari data asset.
 * Bisa terima format frappe.client.get (ada finance_books[])
 * maupun format flat dari Python get_fiscal_assets (ada total_number_of_depreciations langsung).
 */
function populate_row_from_asset(cdt, cdn, asset) {
    const nilai_perolehan = flt(asset.gross_purchase_amount);

    // Ambil total_number_of_depreciations:
    // - dari finance_books[] jika hasil frappe.client.get
    // - langsung dari field jika hasil SQL flat
    let total_dep_komersial = 0;
    if (asset.finance_books && asset.finance_books.length > 0) {
        total_dep_komersial = flt(asset.finance_books[0].total_number_of_depreciations);
    } else {
        total_dep_komersial = flt(asset.total_number_of_depreciations);
    }

    const penyusutan_komersial = total_dep_komersial ? total_dep_komersial / 12 : 0;
    const total_dep_fiskal     = flt(asset.total_depreciation_fiscal);
    const penyusutan_fiskal    = total_dep_fiskal ? total_dep_fiskal / 12 : 0;

    const ppb_kom = penyusutan_komersial ? (nilai_perolehan / penyusutan_komersial) / 12 : 0;
    const ppb_fis = penyusutan_fiskal    ? (nilai_perolehan / penyusutan_fiskal)    / 12 : 0;

    frappe.model.set_value(cdt, cdn, {
        tanggal_perolehan              : asset.purchase_date || null,
        nilai_perolehan                : nilai_perolehan,
        penyusutan_komersial           : penyusutan_komersial,
        penyusutan_fiskal              : penyusutan_fiskal,
        penyusutan_per_bulan_komersial : ppb_kom,
        penyusutan_per_bulan_fiskal    : ppb_fis,
    });
}

function set_asset_filter(frm) {
    frm.fields_dict['report_komersial_dan_fiskal_table'].grid
        .get_field('asset').get_query = function () {
            return {
                filters: [
                    ['Asset', 'fiscal',                '=', 1],
                    ['Asset', 'calculate_depreciation', '=', 1],
                    ['Asset', 'company',               '=', frm.doc.company],
                    ['Asset', 'status',                '=', 'Submitted'],
                ],
            };
        };
}

function get_all_asset(frm) {
    if (!frm.doc.company) {
        frappe.msgprint(__('Harap isi Company terlebih dahulu.'));
        return;
    }
    frappe.confirm(
        __('Tabel akan dikosongkan dan diisi ulang dengan semua Asset milik <b>{0}</b>. Lanjutkan?',
            [frm.doc.company]),
        function () {
            frappe.call({
                // ← sesuaikan path app kamu, contoh: sth.accounting_sth.doctype...
                method: 'sth.accounting_sth.doctype.report_komersial_dan_fiskal.report_komersial_dan_fiskal.get_fiscal_assets',
                args  : { company: frm.doc.company },
                freeze: true,
                freeze_message: __('Mengambil data Asset...'),
                callback(r) {
                    if (r.exc || !r.message || !r.message.length) {
                        frappe.msgprint(__('Tidak ada Asset ditemukan untuk company ini.'));
                        return;
                    }

                    frm.clear_table('report_komersial_dan_fiskal_table');

                    r.message.forEach(asset => {
                        const row = frm.add_child('report_komersial_dan_fiskal_table');
                        // Set asset name LANGSUNG ke row (tidak trigger event)
                        // lalu populate semua field via shared function
                        row.asset = asset.name;
                        populate_row_from_asset(row.doctype, row.name, asset);
                    });

                    frm.refresh_field('report_komersial_dan_fiskal_table');
                    frappe.show_alert({
                        message  : __(`${r.message.length} Asset berhasil dimuat.`),
                        indicator: 'green',
                    });
                    regenerate_tabel_turunan(frm);
                },
            });
        }
    );
}

function regenerate_tabel_turunan(frm) {
    // Hanya jalankan jika tahun sudah diisi
    if (frm.doc.tahun_cek_nilai)   frm.trigger('tahun_cek_nilai');
    if (frm.doc.tahun_cek_selisih) frm.trigger('tahun_cek_selisih');
}

/**
 * Hitung selisih bulan antara dua tanggal (string 'YYYY-MM-DD').
 * Hasil = jumlah bulan dari tgl_mulai ke tgl_akhir (inklusif bulan mulai).
 */
function selisih_bulan(tgl_mulai, tgl_akhir) {
    const mulai = frappe.datetime.str_to_obj(tgl_mulai);
    const akhir = frappe.datetime.str_to_obj(tgl_akhir);

    const tahun  = akhir.getFullYear()  - mulai.getFullYear();
    const bulan  = akhir.getMonth()     - mulai.getMonth();

    return (tahun * 12) + bulan;
}