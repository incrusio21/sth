// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Buku Kerja Mandor Bengkel", {
  refresh(frm) {
    frm.set_query("employee", "table_kryn", function (doc, cdt, cdn) {
      return {
        query: "sth.plantation.doctype.buku_kerja_mandor_bengkel.buku_kerja_mandor_bengkel.get_employee_traksi_query"
      };
    });
  },
});
