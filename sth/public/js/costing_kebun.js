// Costing Panen dan Costing Perawatan isinya sama persis, cuma beda sumber
// kegiatan, jadi tombol Ambil Data-nya dipasang dari satu tempat. Sumbernya
// ditentukan doctype di sisi server, bukan dititipkan dari sini.

function pasang_tombol_costing_kebun(frm) {
    if (frm.doc.docstatus !== 0) {
        return;
    }

    frm.add_custom_button(__("Ambil Data"), () => {
        frm.call({
            doc: frm.doc,
            method: "ambil_data",
            freeze: true,
            freeze_message: __("Mengambil data...")
        }).then(() => {
            frm.refresh_fields();
            peringatkan_data_kurang_kebun(frm);
            frappe.show_alert({ message: __("Data berhasil diambil."), indicator: "green" });
        });
    });
}

// Baris tanpa COA atau Cost Center akan jatuh ke akun/cost center default dan
// merusak pembagian per kegiatan, jadi lebih baik ketahuan sebelum disubmit.
function peringatkan_data_kurang_kebun(frm) {
    const baris = (frm.doc.costing_kebun_closing || []).filter((r) => r.debit);
    const tanpa_coa = baris.filter((r) => !r.no_coa);
    const tanpa_cc = baris.filter((r) => !r.cost_center);

    const pesan = [];

    if (tanpa_coa.length) {
        pesan.push(
            __("Kegiatan berikut belum punya akun di BKM-nya: ") +
            "<b>" + tanpa_coa.map((r) => r.kegiatan || "-").join(", ") + "</b>"
        );
    }

    if (tanpa_cc.length) {
        pesan.push(
            __("Kegiatan berikut belum punya Cost Center: ") +
            "<b>" + tanpa_cc.map((r) => r.kegiatan || "-").join(", ") + "</b>"
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

frappe.ui.form.on("Costing Panen", {
    refresh: pasang_tombol_costing_kebun
});

frappe.ui.form.on("Costing Perawatan", {
    refresh: pasang_tombol_costing_kebun
});
