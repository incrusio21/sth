// Copyright (c) 2026, DAS and Contributors
// MIT License. See license.txt

frappe.provide("sth.sounding");

sth.sounding = {
    // Dipakai Sounding Stock CPO di BST dan Sounding Stock Palm Kernel di
    // Bunker Kernel. Dua form itu beda field dan beda method, tapi tombolnya
    // memanggil method bernama sama — hitung_ulang — yang di server sudah
    // dibedakan lewat REKAP_SOUNDING, jadi tombolnya cukup satu di sini.
    buat_tombol_hitung_ulang: function (frm, opsi) {
        // Cuma untuk dokumen yang sudah disubmit. Selagi draft yang dipakai
        // tombol Get Data, yang sekalian membaca ulang isi soundingnya.
        if (frm.doc.docstatus != 1) return

        opsi = opsi || {}
        const rekap = opsi.rekap || __("rekap")

        frm.add_custom_button(__('Hitung Ulang'), function () {
            frappe.confirm(
                __('Hitung ulang {0} untuk {1} ke atas di unit {2}?<br><br>Stock Entry yang jadi tidak cocok lagi akan dibatalkan dan dibuat ulang.',
                    [rekap, frappe.datetime.str_to_user(frm.doc.tanggal_proses), frm.doc.unit]),
                function () {
                    frappe.dom.freeze(__('Menghitung ulang...'))

                    frm.call('hitung_ulang').then((r) => {
                        frappe.dom.unfreeze()
                        if (!r.message) return

                        sth.sounding.lapor_hitung_ulang(r.message)
                        frm.reload_doc()
                    }, () => frappe.dom.unfreeze())
                }
            )
        })
    },

    lapor_hitung_ulang: function (hasil) {
        frappe.msgprint({
            title: __('Hitung Ulang'),
            message: [
                __('{0} dokumen ditelusuri, {1} angkanya berubah.', [hasil.dokumen, hasil.angka]),
                __('{0} Stock Entry dibuat ulang.', [hasil.ste])
            ].join('<br>'),
            indicator: 'green'
        })
    }
}
