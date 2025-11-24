frappe.ui.form.on("Exit Interview", {
    refresh(frm){
        btnCreatePerhitunganPHK(frm);
        frm.set_value('ref_doctype', 'Perhitungan Kompensasi PHK');
    }
})

function btnCreatePerhitunganPHK(frm) {
    if (frm.doc.reference_document_name || frm.doc.docstatus != 1) {
        return
    }
    frm.add_custom_button('Perhitungan Kompensasi PHK', () => {
        frappe.model.open_mapped_doc({
            method: "sth.overrides.exit_interview.make_perhitungan_kompensasi_phk",
            frm: frm,
        })
    }, 'Create')
}