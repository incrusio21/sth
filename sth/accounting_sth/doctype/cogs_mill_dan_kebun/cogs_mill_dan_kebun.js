frappe.ui.form.on("COGS Mill dan Kebun", {
    refresh(frm) {
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__("Ambil Data"), () => {
                ambil_data_cogs(frm);
            });
        }

        frm.set_intro(null);
        if (frm.doc.buat_stock_reconciliation) {
            frm.set_intro(
                __("Submit akan membuat Stock Reconciliation per produk per unit, menyamakan nilai persediaan di tiap gudang dengan rate Closing Stock. Tabel Closing di bawah tidak diposting karena akun persediaannya sudah disentuh Stock Reconciliation."),
                "blue"
            );
        } else if (!frm.doc.posting_jurnal) {
            frm.set_intro(
                __("Posting Jurnal ke Buku Besar masih mati. Tabel Closing di bawah adalah jurnal yang akan terbentuk, tapi belum ada GL Entry yang dibuat."),
                "orange"
            );
        }
    },

    biaya_kebun(frm) {
        hitung_ulang_cogs(frm);
    },

    biaya_mill(frm) {
        hitung_ulang_cogs(frm);
    },

    harga_rata_cpo(frm) {
        hitung_ulang_cogs(frm);
    },

    harga_rata_pk(frm) {
        hitung_ulang_cogs(frm);
    },

    posting_jurnal(frm) {
        if (frm.doc.posting_jurnal && frm.doc.buat_stock_reconciliation) {
            frm.set_value("buat_stock_reconciliation", 0);
        }
        frm.trigger("refresh");
    },

    buat_stock_reconciliation(frm) {
        if (frm.doc.buat_stock_reconciliation && frm.doc.posting_jurnal) {
            frm.set_value("posting_jurnal", 0);
        }
        frm.trigger("refresh");
    },

    onload(frm) {
        frm.set_query("no_coa", "closing", () => {
            return { filters: { company: frm.doc.company, is_group: 0 } };
        });
        frm.set_query("cost_center", "closing", () => {
            return { filters: { company: frm.doc.company, is_group: 0 } };
        });
    }
});

// Empat field di atas boleh diketik manual dan ikut menentukan nilai baris
// Production. Perhitungannya tidak diulang di sini, tapi dilempar balik ke
// hitung() di server -- rumus yang sama dengan yang jalan waktu disave, jadi
// angka yang kelihatan di form tidak pernah beda dengan yang tersimpan.
function hitung_ulang_cogs(frm) {
    if (frm.doc.docstatus !== 0) {
        return;
    }

    frm.call({
        doc: frm.doc,
        method: "hitung_ulang",
        freeze: true,
        freeze_message: __("Menghitung ulang...")
    }).then(() => {
        frm.refresh_fields();
    });
}

function ambil_data_cogs(frm) {
    if (!frm.doc.periode_dari || !frm.doc.periode_sampai) {
        frappe.msgprint(__("Harap isi Periode Dari dan Periode Sampai terlebih dahulu."));
        return;
    }

    if (!frm.doc.company) {
        frappe.msgprint(__("Harap isi Company terlebih dahulu."));
        return;
    }

    // Dokumennya ikut dikirim supaya server bisa menjalankan hitung() dan
    // mengembalikan baris turunan yang sudah terisi, bukan cuma baris masukan.
    frm.call({
        doc: frm.doc,
        method: "ambil_data",
        freeze: true,
        freeze_message: __("Mengambil data...")
    }).then((r) => {
        frm.refresh_fields();

        const peringatan = r.message || [];
        if (peringatan.length) {
            frappe.msgprint({
                title: __("Perlu Dilengkapi"),
                message: peringatan.join("<br>"),
                indicator: "orange"
            });
        } else {
            frappe.show_alert({ message: __("Data berhasil diambil."), indicator: "green" });
        }
    });
}
