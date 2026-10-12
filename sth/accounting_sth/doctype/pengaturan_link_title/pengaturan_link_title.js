// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pengaturan Link Title", {
	refresh(frm) {
		// Tabel anak dan Single tidak pernah dituju field Link.
		frm.set_query("document_type", "doctype_link_title", () => ({
			filters: { istable: 0, issingle: 0 },
		}));
		frm.set_query("di_doctype", "pengecualian", () => ({
			filters: { istable: 0 },
		}));
		frm.set_query("document_type", "pengecualian", () => ({
			filters: { istable: 0, issingle: 0 },
		}));
	},
});

frappe.ui.form.on("Pengaturan Link Title Doctype", {
	// Title Field diisi dengan title field doctype-nya sekarang, supaya baris baru
	// langsung bisa disimpan dan yang diganti cuma yang memang perlu.
	document_type(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.document_type || row.title_field) return;

		frappe.model.with_doctype(row.document_type, () => {
			const title_field = frappe.get_meta(row.document_type).title_field;
			if (title_field) {
				frappe.model.set_value(cdt, cdn, "title_field", title_field);
			}
		});
	},
});
