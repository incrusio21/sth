frappe.ui.form.on("Costing Bengkel", {
    refresh(frm) {
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__("Ambil Data"), () => {
                ambil_data_bengkel(frm);
            });
        }

        if (!frm.is_new()) {
            frm.add_custom_button(__("Lihat Report Summary"), () => {
                frappe.set_route("query-report", "Costing Bengkel Summary", {
                    costing_bengkel: frm.doc.name
                });
            });
        }
    }
});

function ambil_data_bengkel(frm) {
    if (!frm.doc.periode_dari || !frm.doc.periode_sampai) {
        frappe.msgprint(__("Harap isi Periode Dari dan Periode Sampai terlebih dahulu."));
        return;
    }

    if (!frm.doc.company) {
        frappe.msgprint(__("Harap isi Company terlebih dahulu."));
        return;
    }

    const args = {
        periode_dari: frm.doc.periode_dari,
        periode_sampai: frm.doc.periode_sampai,
        company: frm.doc.company
    };

    frappe.dom.freeze(__("Mengambil data..."));

    Promise.all([
        frappe.call({
            method: "sth.accounting_sth.doctype.costing_bengkel.costing_bengkel.get_pengeluaran_barang_bengkel",
            args
        }),
        frappe.call({
            method: "sth.accounting_sth.doctype.costing_bengkel.costing_bengkel.get_pengeluaran_barang_solar_bengkel",
            args
        }),
        frappe.call({
            method: "sth.accounting_sth.doctype.costing_bengkel.costing_bengkel.get_payslip_karyawan_bengkel",
            args
        }),
        frappe.call({
            method: "sth.accounting_sth.doctype.costing_bengkel.costing_bengkel.get_payslip_operator_vra_bengkel",
            args
        }),
        frappe.call({
            method: "sth.accounting_sth.doctype.costing_bengkel.costing_bengkel.get_wkt_prb_bengkel",
            args
        }),
        frappe.call({
            method: "sth.accounting_sth.doctype.costing_bengkel.costing_bengkel.get_coa_alokasi_gaji_bengkel",
            args: { company: frm.doc.company }
        }),
        frappe.call({
            method: "sth.accounting_sth.doctype.costing_bengkel.costing_bengkel.get_coa_reparasi_bengkel",
            args: { company: frm.doc.company }
        }),
        frappe.call({
            method: "sth.accounting_sth.doctype.costing_bengkel.costing_bengkel.get_coa_biaya_bengkel_dialokasi",
            args: { company: frm.doc.company }
        })
    ]).then(([pb_res, pb_solar_res, payslip_res, payslip_opr_res, wkt_prb_res, coa_res, coa_reparasi_res, coa_dialokasi_res]) => {
        const pb_rows = pb_res.message || [];
        const pb_solar_rows = pb_solar_res.message || [];
        const payslip_rows = payslip_res.message || [];
        const payslip_opr_rows = payslip_opr_res.message || [];
        const wkt_prb_rows = wkt_prb_res.message || [];
        const coa_alokasi = coa_res.message || null;
        const coa_reparasi = coa_reparasi_res.message || null;
        const coa_dialokasi = coa_dialokasi_res.message || null;

        // Pengeluaran Barang Suku Cadang
        frm.clear_table("costing_bengkel_pengeluaran_barang");
        pb_rows.forEach(row => {
            let d = frm.add_child("costing_bengkel_pengeluaran_barang");
            d.pengeluaran_barang = row.pengeluaran_barang;
            d.kode_vra = row.kode_vra;
            d.no_coa = row.no_coa;
            d.amount = row.amount;
            d.keterangan = row.keterangan;
        });

        // Pengeluaran Barang Solar
        frm.clear_table("costing_bengkel_pengeluaran_barang_solar");
        pb_solar_rows.forEach(row => {
            let d = frm.add_child("costing_bengkel_pengeluaran_barang_solar");
            d.pengeluaran_barang = row.pengeluaran_barang;
            d.kode_vra = row.kode_vra;
            d.no_coa = row.no_coa;
            d.amount = row.amount;
            d.keterangan = row.keterangan;
        });

        // Payslip Karyawan Bengkel
        frm.clear_table("costing_bengkel_payslip_karyawan_bengkel");
        payslip_rows.forEach(row => {
            let d = frm.add_child("costing_bengkel_payslip_karyawan_bengkel");
            d.payroll_no = row.no_dokumen;
            d.no_coa = row.no_coa;
            d.amount = row.amount;
            d.keterangan = row.keterangan;
        });

        // Alokasi Gaji Karyawan Bengkel — auto hitung berdasarkan waktu perbaikan (wkt_prb)
        // dari Buku Kerja Mandor Bengkel: rate per jam = total_payslip / total_wkt_prb,
        // lalu tiap kendaraan dapat wkt_prb kendaraan tsb * rate per jam.
        frm.clear_table("costing_bengkel_alokasi_gaji_karyawan_bengkel");
        const total_payslip = payslip_rows.reduce((s, r) => s + (r.amount || 0), 0);
        const total_wkt_prb = wkt_prb_rows.reduce((s, r) => s + (r.total_wkt_prb || 0), 0);
        const rate_per_jam = total_wkt_prb > 0 ? total_payslip / total_wkt_prb : 0;

        const alokasi_gaji_map = {};
        wkt_prb_rows.forEach(r => {
            alokasi_gaji_map[r.kendaraan] = (r.total_wkt_prb || 0) * rate_per_jam;
        });

        Object.keys(alokasi_gaji_map).forEach(kendaraan => {
            let d = frm.add_child("costing_bengkel_alokasi_gaji_karyawan_bengkel");
            d.kode_vra = kendaraan;
            d.no_coa = coa_alokasi;
            d.amount = alokasi_gaji_map[kendaraan];
            d.keterangan = "ALOKASI GAJI KARYAWAN BENGKEL";
        });

        const unique_vra = [...new Set([
            ...Object.keys(alokasi_gaji_map),
            ...pb_rows.map(r => r.kode_vra).filter(Boolean)
        ])];

        // Closing Bengkel — 2 baris per kendaraan (dari Alokasi Gaji Karyawan Bengkel)
        frm.clear_table("costing_bengkel_closing_bengkel");
        unique_vra.forEach(kendaraan => {
            const total_pb_kendaraan = pb_rows
                .filter(r => r.kode_vra === kendaraan)
                .reduce((s, r) => s + (r.amount || 0), 0);
            const amount_per_kendaraan = alokasi_gaji_map[kendaraan] || 0;
            const closing_amount = total_pb_kendaraan + amount_per_kendaraan;

            let debit_row = frm.add_child("costing_bengkel_closing_bengkel");
            debit_row.no_coa = coa_reparasi;
            debit_row.debit = closing_amount;
            debit_row.credit = 0;
            debit_row.kode_vra = kendaraan;
            debit_row.keterangan = "ALOKASI BIAYA BENGKEL KE VRA " + kendaraan;

            let credit_row = frm.add_child("costing_bengkel_closing_bengkel");
            credit_row.no_coa = coa_dialokasi;
            credit_row.debit = 0;
            credit_row.credit = closing_amount;
            credit_row.kode_vra = kendaraan;
            credit_row.keterangan = "ALOKASI BIAYA BENGKEL KE VRA " + kendaraan;
        });

        // Payslip Operator VRA
        frm.clear_table("costing_bengkel_payslip_operator_vra");
        payslip_opr_rows.forEach(row => {
            let d = frm.add_child("costing_bengkel_payslip_operator_vra");
            d.payroll_no = row.no_dokumen;
            d.no_coa = row.no_coa;
            d.amount = row.amount;
            d.keterangan = row.keterangan;
        });

        // Alokasi Gaji Operator VRA — auto hitung, menggunakan kendaraan dari Pengeluaran Barang Solar
        frm.clear_table("costing_bengkel_alokasi_gaji_operator_vra");
        const unique_vra_solar = [...new Set(pb_solar_rows.map(r => r.kode_vra).filter(Boolean))];
        const total_payslip_opr = payslip_opr_rows.reduce((s, r) => s + (r.amount || 0), 0);
        const jumlah_kendaraan_solar = unique_vra_solar.length;
        const amount_per_kendaraan_opr = jumlah_kendaraan_solar > 0 ? total_payslip_opr / jumlah_kendaraan_solar : 0;

        unique_vra_solar.forEach(kendaraan => {
            let d = frm.add_child("costing_bengkel_alokasi_gaji_operator_vra");
            d.kode_vra = kendaraan;
            d.no_coa = coa_alokasi;
            d.amount = amount_per_kendaraan_opr;
            d.keterangan = "ALOKASI GAJI OPERATOR VRA";
        });

        // Hitung total
        const total_pb = pb_rows.reduce((s, r) => s + (r.amount || 0), 0);
        const total_pb_solar = pb_solar_rows.reduce((s, r) => s + (r.amount || 0), 0);
        const total_alokasi = Object.values(alokasi_gaji_map).reduce((s, v) => s + (v || 0), 0);
        const total_alokasi_opr = amount_per_kendaraan_opr * jumlah_kendaraan_solar;

        frm.set_value("total_pengeluaran_barang", total_pb);
        frm.set_value("total_pengeluaran_barang_solar", total_pb_solar);
        frm.set_value("total_payslip_karyawan_bengkel", total_payslip);
        frm.set_value("total_alokasi_gaji_karyawan_bengkel", total_alokasi);
        frm.set_value("total_payslip_operator_vra", total_payslip_opr);
        frm.set_value("total_alokasi_gaji_operator_vra", total_alokasi_opr);

        // GL BKM Traksi & Closing VRA — diambil dari SEMUA BKM Traksi company/unit pada periode tsb,
        // tidak lagi bergantung pada kendaraan yang muncul di Pengeluaran Barang Solar.
        // Closing VRA — account diambil dari task -> kegiatan -> items Kegiatan, dipasangkan credit ke 4112099
        Promise.all([
            frappe.call({
                method: "sth.accounting_sth.doctype.costing_bengkel.costing_bengkel.get_closing_vra_bengkel",
                args: {
                    periode_dari: frm.doc.periode_dari,
                    periode_sampai: frm.doc.periode_sampai,
                    company: frm.doc.company,
                    unit: frm.doc.unit
                }
            }),
            frappe.call({
                method: "sth.accounting_sth.doctype.costing_bengkel.costing_bengkel.get_gl_bkm_traksi_bengkel",
                args: {
                    periode_dari: frm.doc.periode_dari,
                    periode_sampai: frm.doc.periode_sampai,
                    company: frm.doc.company,
                    unit: frm.doc.unit
                }
            })
        ]).then(([closing_vra_res, gl_bkm_traksi_res]) => {
            const closing_vra_rows = closing_vra_res.message || [];
            const gl_bkm_traksi_rows = gl_bkm_traksi_res.message || [];

            frm.clear_table("costing_bengkel_closing_vra");
            closing_vra_rows.forEach(row => {
                let d = frm.add_child("costing_bengkel_closing_vra");
                d.bkm_traksi = row.bkm_traksi;
                d.no_coa = row.no_coa;
                d.debit = row.debit;
                d.credit = row.credit;
                d.kode_vra = row.kode_vra;
                d.keterangan = row.keterangan;
            });

            frm.clear_table("costing_bengkel_gl_bkm_traksi");
            gl_bkm_traksi_rows.forEach(row => {
                let d = frm.add_child("costing_bengkel_gl_bkm_traksi");
                d.bkm_traksi = row.bkm_traksi;
                d.no_coa = row.no_coa;
                d.debit = row.debit;
                d.credit = row.credit;
                d.kode_vra = row.kode_vra;
                d.keterangan = row.keterangan;
            });

            const total_closing_vra = closing_vra_rows.reduce((s, r) => s + (r.debit || 0), 0);
            const total_gl_bkm_traksi = gl_bkm_traksi_rows.reduce((s, r) => s + (r.debit || 0), 0);
            frm.set_value("total_closing_vra", total_closing_vra);
            frm.set_value("total_gl_bkm_traksi", total_gl_bkm_traksi);

            frm.set_value("grand_total", total_pb + total_pb_solar + total_payslip + total_alokasi + total_payslip_opr + total_alokasi_opr);

            // Kegiatan BKM Traksi — per baris task dari BKM Traksi yang sudah terambil di
            // costing_bengkel_gl_bkm_traksi. Debit = (kmhm_akhir - kmhm_awal) task tsb x Total Cost
            // Per KM/HM kendaraan (dihitung server dari Closing Bengkel + Closing VRA + GL BKM Traksi),
            // account debit dari Kegiatan sesuai company, credit dipasangkan ke 4112099.
            const bkm_traksi_list = [...new Set(gl_bkm_traksi_rows.map(r => r.bkm_traksi).filter(Boolean))];

            frappe.call({
                method: "sth.accounting_sth.doctype.costing_bengkel.costing_bengkel.get_kegiatan_bkm_traksi_bengkel",
                args: {
                    bkm_traksi_list: bkm_traksi_list,
                    periode_dari: frm.doc.periode_dari,
                    periode_sampai: frm.doc.periode_sampai,
                    company: frm.doc.company,
                    unit: frm.doc.unit
                }
            }).then(kegiatan_res => {
                const kegiatan_rows = kegiatan_res.message || [];

                frm.clear_table("costing_bengkel_kegiatan_bkm_traksi");
                kegiatan_rows.forEach(row => {
                    let d = frm.add_child("costing_bengkel_kegiatan_bkm_traksi");
                    d.bkm_traksi = row.bkm_traksi;
                    d.no_coa = row.no_coa;
                    d.debit = row.debit;
                    d.credit = row.credit;
                    d.kode_vra = row.kode_vra;
                    d.keterangan = row.keterangan;
                });

                const total_kegiatan_bkm_traksi = kegiatan_rows.reduce((s, r) => s + (r.debit || 0), 0);
                frm.set_value("total_kegiatan_bkm_traksi", total_kegiatan_bkm_traksi);

                frm.refresh_fields();
                frappe.dom.unfreeze();
                frappe.show_alert({ message: __("Data berhasil diambil"), indicator: "green" });
            });
        });
    });
}
