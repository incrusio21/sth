frappe.ui.form.on("Rencana Kerja Olah TBS", {

    jumlah_tbs_restan: function(frm) {
        hitung_total_tbs(frm);
    },

    jumlah_taksasi_tbs_kebun: function(frm) {
        hitung_total_tbs(frm);
    },

    jumlah_taksasi_tbs_luar: function(frm) {
        hitung_total_tbs(frm);
    }

});

function hitung_total_tbs(frm) {

    let restan = flt(frm.doc.jumlah_tbs_restan);
    let kebun = flt(frm.doc.jumlah_taksasi_tbs_kebun);
    let luar = flt(frm.doc.jumlah_taksasi_tbs_luar);

    let total = restan + kebun + luar;

    frm.set_value("total_volume_tbs", total);
}