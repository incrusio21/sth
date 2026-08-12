frappe.ui.form.on("Costing Mill", {
    setup(frm) {
        frm.set_query("unit", () => ({ filters: { mill: 1 } }));
    },

    refresh(frm) {
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__("Ambil Data"), () => {
                ambil_data_mill(frm);
            });
        }
    }
});

function ambil_data_mill(frm) {
    if (!frm.doc.periode_dari || !frm.doc.periode_sampai) {
        frappe.msgprint(__("Harap isi Periode Dari dan Periode Sampai terlebih dahulu."));
        return;
    }

    if (!frm.doc.company) {
        frappe.msgprint(__("Harap isi Company terlebih dahulu."));
        return;
    }

    frappe.dom.freeze(__("Mengambil data..."));

    frappe.call({
        method: "sth.accounting_sth.doctype.costing_mill.costing_mill.get_costing_mill_data",
        args: {
            periode_dari: frm.doc.periode_dari,
            periode_sampai: frm.doc.periode_sampai,
            company: frm.doc.company,
            unit: frm.doc.unit
        }
    }).then(res => {
        const data = res.message || {};
        const gaji_rows = data.gaji_karyawan || [];
        const pb_rows = data.pengeluaran_barang || [];
        const bkm_rows = data.bkm || [];
        const stasiun_rows = data.stasiun || [];

        // A. Gaji Karyawan Mill
        frm.clear_table("costing_mill_gaji_karyawan");
        gaji_rows.forEach(row => {
            let d = frm.add_child("costing_mill_gaji_karyawan");
            d.salary_slip = row.salary_slip;
            d.employee = row.employee;
            d.employee_name = row.employee_name;
            d.stasiun = row.stasiun;
            d.no_coa = row.no_coa;
            d.amount = row.amount;
            d.keterangan = row.keterangan;
        });

        // B. Pengeluaran Barang Mill
        frm.clear_table("costing_mill_pengeluaran_barang");
        pb_rows.forEach(row => {
            let d = frm.add_child("costing_mill_pengeluaran_barang");
            d.pengeluaran_barang = row.pengeluaran_barang;
            d.sub_unit = row.sub_unit;
            d.stasiun = row.stasiun;
            d.kode_barang = row.kode_barang;
            d.no_coa = row.no_coa;
            d.amount = row.amount;
            d.keterangan = row.keterangan;
        });

        // C. BKM Bengkel & BKM Traksi
        frm.clear_table("costing_mill_bkm");
        bkm_rows.forEach(row => {
            let d = frm.add_child("costing_mill_bkm");
            d.sumber = row.sumber;
            d.reference_doctype = row.reference_doctype;
            d.no_dokumen = row.no_dokumen;
            d.stasiun = row.stasiun;
            d.no_coa = row.no_coa;
            d.amount = row.amount;
            d.keterangan = row.keterangan;
        });

        // D. Rekap Per Stasiun
        frm.clear_table("costing_mill_stasiun");
        stasiun_rows.forEach(row => {
            let d = frm.add_child("costing_mill_stasiun");
            d.stasiun = row.stasiun;
            d.nama_stasiun = row.nama_stasiun;
            d.cost_center = row.cost_center;
            d.no_coa = row.no_coa;
            d.total_gaji_karyawan = row.total_gaji_karyawan;
            d.total_pengeluaran_barang = row.total_pengeluaran_barang;
            d.total_bkm = row.total_bkm;
            d.total = row.total;
        });

        const total_gaji = gaji_rows.reduce((s, r) => s + (r.amount || 0), 0);
        const total_pb = pb_rows.reduce((s, r) => s + (r.amount || 0), 0);
        const total_bkm = bkm_rows.reduce((s, r) => s + (r.amount || 0), 0);

        frm.set_value("total_gaji_karyawan", total_gaji);
        frm.set_value("total_pengeluaran_barang", total_pb);
        frm.set_value("total_bkm", total_bkm);
        frm.set_value("grand_total", total_gaji + total_pb + total_bkm);

        frm.refresh_fields();
        frappe.dom.unfreeze();
        frappe.show_alert({ message: __("Data berhasil diambil"), indicator: "green" });
    }).catch(() => {
        frappe.dom.unfreeze();
    });
}
