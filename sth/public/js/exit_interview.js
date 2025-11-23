frappe.ui.form.on("Exit Interview", {
    refresh(frm){
        btnCreatePerhitunganPHK(frm);
    }
})

function btnCreatePerhitunganPHK(frm) {
    if (frm.doc.reference_document_name) {
        return
    }
    frm.add_custom_button('Perhitungan Kompensasi PHK', () => {
        frappe.model.open_mapped_doc({
            method: "sth.overrides.exit_interview.make_perhitungan_kompensasi_phk",
            frm: frm,
        })
    }, 'Create')
}