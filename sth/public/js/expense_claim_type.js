frappe.ui.form.on("Expense Claim Type", {
  refresh(frm) {
    frm.set_query("unit", "accounts", function (doc, cdt, cdn) {
      let row = locals[cdt][cdn];

      return {
        filters: {
          company: row.company
        }
      };
    });
  }
});