frappe.ui.form.on("COGS Mill dan Kebun", {
    refresh(frm) {
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__("Ambil Data"), () => {
                ambil_data_cogs(frm);
            });
        }

        if (frm.doc.docstatus > 0 && frm.doc.status_revaluasi === "Gagal") {
            frm.add_custom_button(__("Jalankan Ulang Revaluasi"), () => {
                frm.call({
                    doc: frm.doc,
                    method: "jalankan_ulang_revaluasi",
                    freeze: true
                }).then(() => frm.reload_doc());
            });
        }

        frm.set_intro(null);
        if (frm.doc.docstatus > 0 && frm.doc.status_revaluasi) {
            set_intro_status_revaluasi(frm);
        } else if (frm.doc.docstatus === 0) {
            set_intro_draft(frm);
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

    // Jurnal sekarang cuma kapitalisasi dan tidak menyentuh akun persediaan,
    // jadi ketiga pilihan boleh menyala bersamaan.
    posting_jurnal(frm) {
        frm.trigger("refresh");
    },

    buat_stock_reconciliation(frm) {
        frm.trigger("refresh");
    },

    revaluasi_hpp(frm) {
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

function set_intro_draft(frm) {
    const langkah = [];
    if (frm.doc.posting_jurnal) {
        langkah.push(__("memposting jurnal kapitalisasi di tabel Closing"));
    }
    if (frm.doc.revaluasi_hpp) {
        langkah.push(__("mengganti rate masuk Stock Entry produksi TBS, CPO, dan PK bulan ini dengan rate hasil perhitungan, lalu menilai ulang semua transaksi stok sesudahnya — termasuk HPP Delivery Note dan gudang transit"));
    }
    if (frm.doc.buat_stock_reconciliation) {
        langkah.push(frm.doc.revaluasi_hpp
            ? __("membuat Stock Reconciliation untuk sisa selisih terhadap Closing Stock")
            : __("membuat Stock Reconciliation yang menyamakan nilai tiap gudang dengan rate Closing Stock"));
    }

    if (!langkah.length) {
        frm.set_intro(
            __("Tidak ada yang diposting waktu submit: jurnal, revaluasi, dan Stock Reconciliation semuanya mati."),
            "orange"
        );
        return;
    }

    let pesan = __("Submit akan") + " " + langkah.join("; ") + ".";
    if (frm.doc.revaluasi_hpp) {
        pesan += " " + __("Revaluasi berjalan di background dan rate asal dicatat supaya bisa dikembalikan waktu cancel.");
    }
    frm.set_intro(pesan, frm.doc.posting_jurnal ? "blue" : "orange");
}

function set_intro_status_revaluasi(frm) {
    const status = frm.doc.status_revaluasi;
    const pesan = {
        "Antri": [__("Revaluasi HPP menunggu giliran di background."), "blue"],
        "Berjalan": [__("Revaluasi HPP sedang berjalan. Muat ulang dokumen untuk melihat hasilnya."), "blue"],
        "Selesai": [__("Revaluasi HPP selesai."), "green"],
        "Dipulihkan": [__("Rate asal Stock Entry produksi sudah dikembalikan."), "green"],
        "Gagal": [__("Revaluasi HPP gagal. Lihat Catatan Revaluasi, perbaiki penyebabnya, lalu klik Jalankan Ulang Revaluasi."), "red"]
    }[status];

    if (pesan) {
        frm.set_intro(pesan[0], pesan[1]);
    }
}

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
        frm.dirty()

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
