// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Surat Menyurat", {
  setup(frm) {
    frm.set_query("unit", function (doc) {
      return {
        filters: {
          company: doc.company
        }
      };
    });
  },

  company(frm) {
    frm.set_value("unit", "");
    frm.refresh_field("unit");
  }
});