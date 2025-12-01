// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt
frappe.provide("sth.queries")
frappe.ui.form.on("Berita Acara", {
    onload(frm) {
        frm.set_query("item_code", "table_klkc", sth.queries.item_by_subtype)
    },
});
