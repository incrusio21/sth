// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Data TBS", {
    refresh(frm) {
        buat_tombol_hitung_ulang(frm)
    },

    get_data(frm) {
        frm.call("get_data").then(() => {
            frm.dirty()
            frm.refresh()
        })
    }
});

function buat_tombol_hitung_ulang(frm){
    // Cuma untuk dokumen yang sudah disubmit. Selagi draft yang dipakai Get
    // Data, yang sekalian membaca ulang lori dan jam olah.
    if (frm.doc.docstatus != 1) return

    frm.add_custom_button(__('Hitung Ulang'), function() {
        frappe.confirm(
            __('Hitung ulang TBS diterima dan restan untuk {0} ke atas di unit {1}?<br><br>Stock Entry harian yang jadi tidak cocok lagi akan dibatalkan dan dibuat ulang.',
                [frappe.datetime.str_to_user(frm.doc.tanggal_produksi), frm.doc.unit]),
            function() {
                frappe.dom.freeze(__('Menghitung ulang...'))

                frm.call('hitung_ulang').then((r) => {
                    frappe.dom.unfreeze()
                    if (!r.message) return

                    lapor_hitung_ulang(r.message)
                    frm.reload_doc()
                }, () => frappe.dom.unfreeze())
            }
        )
    })
}

function lapor_hitung_ulang(hasil){
    let pesan = [
        __('{0} Data TBS ditelusuri, {1} angkanya berubah.', [hasil.dokumen, hasil.angka]),
        __('{0} Stock Entry dibuat ulang.', [hasil.ste])
    ]

    // Hari yang punya lebih dari satu Data TBS hidup dilewati server: timbangan
    // sehari penuh tidak bisa dibagi ke dua dokumen tanpa menebak.
    if (hasil.kembar && hasil.kembar.length) {
        pesan.push(__('Dilewati karena tanggalnya dipakai lebih dari satu dokumen: {0}.',
            [hasil.kembar.join(', ')]))
    }

    frappe.msgprint({
        title: __('Hitung Ulang'),
        message: pesan.join('<br>'),
        indicator: 'green'
    })
}
