// Client Script – Payment Entry (Leasing)
// Daftarkan di: Customize Form → Payment Entry → Client Script
// ATAU simpan sebagai file JS di dalam folder public/js aplikasi kamu.
//
// Prasyarat custom field di Payment Entry (tambahkan via Customize Form):
//   - tipe_transfer        : Select  (sudah ada)
//   - transaksi_berulang   : Link → Transaksi Berulang  (sudah ada)
//   - leasing_row_idx      : Int, hidden  ← BARU, wajib ditambah

frappe.ui.form.on("Payment Entry", {

    // ─── Refresh: tombol "Ganti Angsuran" saat draft & Leasing ───────────────
    refresh(frm) {

        if (
            frm.doc.tipe_transfer === "Leasing" &&
            frm.doc.transaksi_berulang &&
            frm.doc.docstatus === 0
        ) {
            frm.add_custom_button(__("Ganti Angsuran"), () => {
                _show_angsuran_picker(frm);
            }, __("Leasing"));
        }

        frm.set_query('transaksi_berulang', function () {
            return {
                filters: {
                    company: frm.doc.company,
                    docstatus:1,
                    jenis_transaksi:"LEASING"
                }
            };
        });
    },

    // ─── tipe_transfer berubah ────────────────────────────────────────────────
    tipe_transfer(frm) {
        if (frm.doc.tipe_transfer !== "Leasing") {
            frm.set_value("transaksi_berulang", null);
            frm.set_value("leasing_row_idx", null);
        }
    },

    // ─── transaksi_berulang diisi → langsung buka picker ─────────────────────
    transaksi_berulang(frm) {
        if (frm.doc.tipe_transfer === "Leasing" && frm.doc.transaksi_berulang) {
            // Reset pilihan lama dulu
            frm.set_value("leasing_row_idx", null);
            _show_angsuran_picker(frm);
        }
    },
});


// ─── Helpers ──────────────────────────────────────────────────────────────────




/** Ambil baris Leasing lalu tampilkan dialog tabel */
function _show_angsuran_picker(frm) {
    frappe.call({
        method: "sth.custom.leasing_api.get_leasing_rows",   // ← ganti nama_app
        args: { docname: frm.doc.transaksi_berulang },
        freeze: true,
        freeze_message: __("Mengambil data angsuran…"),
        callback(r) {
            if (!r.message) return;

            const { rows, meta } = r.message;

            if (!rows.length) {
                frappe.msgprint({
                    title: __("Info"),
                    message: __("Semua angsuran untuk dokumen ini sudah dibayar."),
                    indicator: "green",
                });
                return;
            }

            _open_picker_dialog(frm, rows, meta);
        },
    });
}


/** Buka dialog dengan tabel angsuran yang bisa diklik */
function _open_picker_dialog(frm, rows, meta) {
    // Baris yang sudah dipilih sebelumnya (highlight)
    const current_idx = frm.doc.leasing_row_idx;

    const table_rows_html = rows.map(row => {
        const is_current = row.idx === current_idx;
        const angsuran = parseFloat(row.angsuran) || 0;
        const bunga    = parseFloat(row.bunga)    || 0;
        const saldo    = parseFloat(row.saldo)    || 0;
        const total    = angsuran + bunga;

        const fmt = n => Math.round(n).toLocaleString('id-ID');

        return `
            <tr class="Leasing-row-pick ${is_current ? "table-primary" : ""}"
                data-idx="${row.idx}"
                style="cursor:pointer;">
                <td class="text-center">${row.tenor}</td>
                <td>${frappe.datetime.str_to_user(row.tanggal_angsuran)}</td>
                <td class="text-right">${fmt(angsuran)}</td>
                <td class="text-right">${fmt(bunga)}</td>
                <td class="text-right"><strong>${fmt(total)}</strong></td>
                <td class="text-right">${fmt(saldo)}</td>
            </tr>`;
    }).join("");

    const table_html = `
        <style>
            .Leasing-row-pick:hover { background: var(--bg-color, #f4f5f7) !important; }
        </style>
        <div style="overflow-x:auto; max-height:360px; overflow-y:auto;">
            <table class="table table-bordered table-sm mb-0">
                <thead class="thead-dark">
                    <tr>
                        <th class="text-center">Tenor</th>
                        <th>Tgl Angsuran</th>
                        <th class="text-right">Angsuran</th>
                        <th class="text-right">Bunga</th>
                        <th class="text-right">Total</th>
                        <th class="text-right">Saldo</th>
                    </tr>
                </thead>
                <tbody>
                    ${table_rows_html}
                </tbody>
            </table>
        </div>
        <p class="text-muted small mt-2">
            <i class="fa fa-info-circle"></i>
            Klik salah satu baris untuk mengisi Payment Entry secara otomatis.
        </p>`;

    const d = new frappe.ui.Dialog({
        title: __("Pilih Angsuran Leasing – {0}", [frm.doc.transaksi_berulang]),
        fields: [{
            fieldtype : "HTML",
            fieldname : "tabel_angsuran",
            options   : table_html,
        }],
        size: "large",
    });

    d.show();

    // ─── Klik baris ─────────────────────────────────────────────────────────
    d.$wrapper.find(".Leasing-row-pick").on("click", function () {
        const idx = parseInt($(this).data("idx"));
        const row = rows.find(r => r.idx === idx);
        if (!row) return;

        _apply_Leasing_row(frm, row, meta);
        d.hide();
    });
}


/**
 * Isi Payment Entry berdasarkan baris Leasing yang dipilih.
 * payment_type = Internal Transfer
 *   paid_from  = jurnal_kredit  (kredit: angsuran + bunga keluar)
 *   paid_to    = jurnal_debit   (debit : angsuran masuk / lunasi liability)
 *   deductions = biaya_bunga    (selisih bunga)
 */
function _apply_Leasing_row(frm, row, meta) {
    const total = row.angsuran + row.bunga;

    // Simpan idx agar server-side bisa update baris yang benar
    frm.set_value("leasing_row_idx", row.idx);

    // Tanggal posting = tanggal angsuran
    frm.set_value("posting_date", row.tanggal_angsuran);

    // Tipe & akun
    frm.set_value("payment_type", "Internal Transfer");
    // frm.set_value("paid_from",    meta.jurnal_kredit);
    frm.set_value("paid_to",      meta.jurnal_debit);
    console.log(row.no_transfer)
    frm.set_value("no_rekening_tujuan", row.no_transfer )

    // Nominal
    frm.set_value("paid_amount",     total);
    frm.set_value("received_amount", row.angsuran);

    // Deduction bunga
    frm.clear_table("deductions");
    if (row.bunga && meta.biaya_bunga_leasing_debit) {
        const ded     = frm.add_child("deductions");
        ded.account   = meta.biaya_bunga_leasing_debit;
        ded.amount    = row.bunga;
    }

    frm.refresh_fields();

    frappe.show_alert({
        message  : __(
            "Tenor {0} dipilih — Angsuran: {1}  Bunga: {2}  Total: {3}",
            [row.tenor, (row.angsuran), (row.bunga), (total)]
        ),
        indicator: "green",
    }, 6);
}


