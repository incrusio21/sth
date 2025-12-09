frappe.ui.form.on("Supplier Quotation", {
    refresh(frm) {
        frm.page.btn_secondary.hide()
        if (frm.doc.workflow_state == "Approved") {
            frm.add_custom_button(__("Re open"), function () {
                let rfq = frm.doc.items[0].request_for_quotation
                frappe.xcall("sth.custom.supplier_quotation.reopen_rfq", { name: rfq, freeze: true })
                    .then((res) => {
                        // console.log("Oke")
                        frm.reload_doc()
                    })
            })

        } else {
            frm.remove_custom_button(__("Re open"))
        }
    }
})