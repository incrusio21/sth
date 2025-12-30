// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Buku Kerja Mandor Premi", {
	refresh(frm) {
        frm.disable_save();
		if(in_list(["Panen"], frm.doc.buku_kerja_mandor)){
			frm.fields_dict.amount.set_label("Total Weight");
		}
	},
});
