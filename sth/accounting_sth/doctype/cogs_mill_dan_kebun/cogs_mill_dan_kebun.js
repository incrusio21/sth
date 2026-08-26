frappe.ui.form.on("COGS Mill dan Kebun", {
    refresh(frm) {
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__("Ambil Data"), () => {
                ambil_data_cogs(frm);
            });
        }

        frm.set_intro(null);
        if (!frm.doc.posting_jurnal) {
            frm.set_intro(
                __("Posting Jurnal ke Buku Besar masih mati. Tabel Closing di bawah adalah jurnal yang akan terbentuk, tapi belum ada GL Entry yang dibuat."),
                "orange"
            );
        }
    },

    posting_jurnal(frm) {
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

const METODE = "sth.accounting_sth.doctype.cogs_mill_dan_kebun.cogs_mill_dan_kebun";

function ambil_data_cogs(frm) {
    if (!frm.doc.periode_dari || !frm.doc.periode_sampai) {
        frappe.msgprint(__("Harap isi Periode Dari dan Periode Sampai terlebih dahulu."));
        return;
    }

    if (!frm.doc.company) {
        frappe.msgprint(__("Harap isi Company terlebih dahulu."));
        return;
    }

    // frappe.call mengembalikan promise jQuery yang tidak punya .finally(),
    // jadi pembekuan layar diserahkan ke opsi freeze bawaan.
    frappe.call({
        method: `${METODE}.ambil_data`,
        args: {
            periode_dari: frm.doc.periode_dari,
            periode_sampai: frm.doc.periode_sampai,
            company: frm.doc.company,
            unit: frm.doc.unit
        },
        freeze: true,
        freeze_message: __("Mengambil data..."),
        callback(r) {
            const d = r.message;
            if (!d) return;

            frm.clear_table("rincian");
            (d.rincian || []).forEach((row) => frm.add_child("rincian", row));

            // Nilai berikut boleh dikoreksi manual setelahnya; perhitungan di
            // server selalu jalan ulang waktu dokumen disimpan.
            frm.set_value("biaya_kebun", d.biaya_kebun);
            frm.set_value("biaya_mill", d.biaya_mill);
            frm.set_value("harga_rata_cpo", d.harga_rata_cpo);
            frm.set_value("harga_rata_pk", d.harga_rata_pk);
            frm.set_value("saldo_gl_tbs", d.saldo_gl_tbs);
            frm.set_value("saldo_gl_cpo", d.saldo_gl_cpo);
            frm.set_value("saldo_gl_pk", d.saldo_gl_pk);

            frm.refresh_fields();

            if ((d.peringatan || []).length) {
                frappe.msgprint({
                    title: __("Perlu Dilengkapi"),
                    message: d.peringatan.join("<br>"),
                    indicator: "orange"
                });
            } else {
                frappe.show_alert({ message: __("Data berhasil diambil."), indicator: "green" });
            }
        }
    });
}
