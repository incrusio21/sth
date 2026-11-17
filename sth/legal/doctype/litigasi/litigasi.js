// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Litigasi", {
  refresh(frm) {
    frm.set_query("unit", () => {
      return {
        filters: {
          company: frm.doc.company,
        }
      }
    });
  },
  company(frm) {
    frm.set_query("unit", () => {
      return {
        filters: {
          company: frm.doc.company,
        }
      }
    });
  }
});
