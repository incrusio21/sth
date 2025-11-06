frappe.ui.form.on("Expense Claim", {
  async custom_get_travel_request_expense(frm) {
    if (!(frm.doc.employee)) {
      frappe.msgprint(__("Lengkapi Employee terlebih dahulu."));
      return;
    }

    frm.clear_table("expenses");
    show_expense_selector(frm);

    // const response = await frappe.call({
    //   method: "sth.overrides.expense_claim.get_travel_request_expenses",
    //   args: {
    //     employee: frm.doc.employee,
    //     company: frm.doc.company,
    //     department: frm.doc.department,
    //   },
    // });

    // for (const exp of response.message) {
    //   frm.add_child("expenses", {
    //     expense_date: exp.posting_date,
    //     expense_type: exp.expense_type,
    //     default_account: exp.default_account,
    //     amount: exp.amount,
    //     sanctioned_amount: exp.amount,
    //   })
    // }

    // const test = await frappe.call({
    //   method: "sth.overrides.expense_claim.test_safe_eval"
    // });

    // console.log(test);

    // frm.refresh_field("expenses");
  }
});

async function show_expense_selector(frm) {
  const fields = [
    {
      fieldtype: 'Date',
      fieldname: 'expense_date',
      label: 'Expense Date',
      in_list_view: true
    },
    {
      fieldtype: 'Link',
      fieldname: 'expense_type',
      label: 'Expense Type',
      in_list_view: true
    },
    {
      fieldtype: 'Link',
      fieldname: 'default_account',
      label: 'Default Account',
      in_list_view: true
    },
    {
      fieldtype: 'Currency',
      fieldname: 'amount',
      label: 'Amount',
      in_list_view: true
    },
    {
      fieldtype: 'Currency',
      fieldname: 'sanctioned_amount',
      label: 'Sanctioned_amount',
      in_list_view: true
    },
  ];

  let d = new frappe.ui.Dialog({
    title: 'Select Expense',
    size: 'large',
    fields: [
      {
        label: 'Expenses',
        fieldname: 'expenses',
        fieldtype: 'Table',
        cannot_add_rows: true,
        in_place_edit: false,
        fields: fields
      }
    ],
    primary_action_label: 'Submit',
    primary_action() {
      const selected_items = d.fields_dict.expenses.grid.get_selected_children();

      if (selected_items.length < 1) {
        frappe.throw("Please Select at least One Expense")
      }

      for (const exp of selected_items) {
        frm.add_child("expenses", {
          expense_date: exp.expense_date,
          expense_type: exp.expense_type,
          default_account: exp.default_account,
          amount: exp.amount,
          sanctioned_amount: exp.sanctioned_amount,
        })
      }

      frm.refresh_field("expenses");
      d.hide();
    }
  });

  const response = await frappe.call({
    method: "sth.overrides.expense_claim.get_travel_request_expenses",
    args: {
      employee: frm.doc.employee,
      company: frm.doc.company,
      department: frm.doc.department,
    },
  });

  if (response.message) {
    d.fields_dict.expenses.df.data = response.message;
    d.fields_dict.expenses.refresh();
  }
  d.show();
}