frappe.ui.form.on("Travel Request", {
  refresh(frm) {
  }
});

frappe.ui.form.on("Travel Request Costing", {
  total_amount(frm, cdt, cdn) {
    calculate_total_costing(frm);
  },
  costings_remove(frm, cdt, cdn) {
    calculate_total_costing(frm);
  }
});

function calculate_total_costing(frm) {
  let total = 0;
  (frm.doc.costings || []).forEach(row => {
    total += flt(row.total_amount);
  });
  frm.set_value("custom_grand_total_costing", total);
  frm.refresh_field("custom_grand_total_costing");
}