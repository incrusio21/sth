frappe.ui.form.on("Pencatatan HM Mesin", {

    hm_mesin_awal: hitung_total_hm,
    hm_mesin_akhir: hitung_total_hm

});

function hitung_total_hm(frm) {

    let awal = flt(frm.doc.hm_mesin_awal);
    let akhir = flt(frm.doc.hm_mesin_akhir);

    let total = akhir - awal;

    frm.set_value("total_hm_mesin", total);
}