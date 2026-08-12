frappe.ui.form.on("Costing Mill", {
    refresh(frm) {
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__("Ambil Data"), () => {
                ambil_data_mill(frm);
            });
        }
    }
});

const METODE = "sth.accounting_sth.doctype.costing_mill.costing_mill";

function ambil_data_mill(frm) {
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
        company: frm.doc.company,
        unit: frm.doc.unit
    };

    frappe.dom.freeze(__("Mengambil data..."));

    Promise.all([
        frappe.call({ method: `${METODE}.get_gaji_karyawan_mill`, args }),
        frappe.call({ method: `${METODE}.get_gaji_operator_bengkel_mill`, args }),
        frappe.call({ method: `${METODE}.get_alokasi_hm_stasiun`, args }),
        frappe.call({ method: `${METODE}.get_pengeluaran_barang_mill`, args }),
        frappe.call({ method: `${METODE}.get_closing_mill`, args })
    ]).then(([gaji_res, bengkel_res, hm_res, barang_res, closing_res]) => {
        isi_tabel(frm, "costing_mill_gaji_karyawan", gaji_res.message);
        isi_tabel(frm, "costing_mill_gaji_operator_bengkel", bengkel_res.message);
        isi_tabel(frm, "costing_mill_hm_stasiun", hm_res.message);
        isi_tabel(frm, "costing_mill_pengeluaran_barang", barang_res.message);
        isi_tabel(frm, "costing_mill_closing", closing_res.message);

        frm.refresh_fields();
        peringatkan_data_kurang(frm);

        frappe.show_alert({ message: __("Data berhasil diambil."), indicator: "green" });
    }).catch((err) => {
        frappe.msgprint({
            title: __("Gagal Mengambil Data"),
            message: (err && err.message) || __("Terjadi kesalahan saat mengambil data."),
            indicator: "red"
        });
    }).finally(() => {
        frappe.dom.unfreeze();
    });
}

function isi_tabel(frm, fieldname, rows) {
    frm.clear_table(fieldname);
    (rows || []).forEach((row) => frm.add_child(fieldname, row));
}

// Baris tanpa COA atau Cost Center akan jatuh ke akun/cost center default dan
// merusak pembagian per stasiun, jadi lebih baik ketahuan sebelum disubmit.
function peringatkan_data_kurang(frm) {
    const tanpa_coa = (frm.doc.costing_mill_closing || []).filter((r) => !r.no_coa);
    const tanpa_cc = (frm.doc.costing_mill_closing || []).filter((r) => r.stasiun && !r.cost_center);

    const pesan = [];

    if (tanpa_coa.length) {
        pesan.push(
            __("Stasiun berikut belum ketemu akun OPERASIONAL-nya (cek Station Procurement Settings): ") +
            "<b>" + tanpa_coa.map((r) => r.stasiun || "-").join(", ") + "</b>"
        );
    }

    if (tanpa_cc.length) {
        pesan.push(
            __("Stasiun berikut belum punya Cost Center (cek Detail Station Settings di Station Master): ") +
            "<b>" + tanpa_cc.map((r) => r.stasiun).join(", ") + "</b>"
        );
    }

    if (pesan.length) {
        frappe.msgprint({
            title: __("Perlu Dilengkapi"),
            message: pesan.join("<br><br>"),
            indicator: "orange"
        });
    }
}
