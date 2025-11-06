// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Setup THR", {
// 	refresh(frm) {

// 	},
// });

frappe.ui.form.on("THR Setup Rule", {
  async table_thr_rules_add(frm, cdt, cdn) {
    let row = locals[cdt][cdn];

    const response = await frappe.call({
      method: "get_setup_rate_thr",
      doc: frm.doc
    });

    if (response.message) {
      const { uang_daging, natura_rate, payment_days } = response.message

      frappe.model.set_value(cdt, cdn, "uang_daging", uang_daging);
      frappe.model.set_value(cdt, cdn, "natura_rate", natura_rate);
      frappe.model.set_value(cdt, cdn, "payment_days", payment_days);
    }
  }
});
