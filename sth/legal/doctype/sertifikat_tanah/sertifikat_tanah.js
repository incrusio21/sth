// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sertifikat Tanah", {
  refresh(frm) {
    set_query_field(frm);
  },
});

function set_query_field(frm) {
  frm.set_query("unit", function (doc) {
    return {
      filters: {
        company: doc.company,
      },
    };
  });
}