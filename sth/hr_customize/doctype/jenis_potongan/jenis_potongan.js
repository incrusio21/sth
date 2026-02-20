// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Jenis Potongan", {
// 	refresh(frm) {

// 	},
// });

frappe.ui.form.on("Jenis Potongan Accounts", {
  company: function (frm, cdt, cdn) {
    frm.set_query("expense_account", "potongan_accounts", function (doc, cdt, cdn) {
      let row = locals[cdt][cdn];

      return {
        filters: { company: row.company },
      };
    });

    frm.set_query("unit", "potongan_accounts", function (doc, cdt, cdn) {
      let row = locals[cdt][cdn];

      return {
        filters: {
          company: row.company
        }
      };
    });
  },
  potongan_accounts_add: function (frm, cdt, cdn) {
    frm.set_query("expense_account", "potongan_accounts", function (doc, cdt, cdn) {
      let row = locals[cdt][cdn];

      return {
        filters: { company: row.company },
      };
    });

    frm.set_query("unit", "potongan_accounts", function (doc, cdt, cdn) {
      let row = locals[cdt][cdn];
      console.log(row.company);
      return {
        filters: {
          company: row.company
        }
      };
    });
  },
});
