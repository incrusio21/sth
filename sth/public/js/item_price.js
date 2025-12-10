
frappe.ui.form.on("Item Price", {
	tambahan(frm) {
		if(frm.doc.tambahan && frm.doc.price_list_rate){
			frm.doc.price_list_rate = frm.doc.price_list_rate + frm.doc.tambahan
			frm.doc.tambahan = 0
			frm.refresh_fields()
		}
	}
})