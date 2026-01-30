frappe.ui.form.on("Expense Claim", {
  refresh(frm) {
    if (frm.doc.docstatus == 0 || frm.is_new()) {
      frm.add_custom_button(
        __("Get Travel Request Expense"),
        function () {
          if (!(frm.doc.employee)) {
            frappe.msgprint(__("Lengkapi Employee terlebih dahulu."));
            return;
          }
          if (!(frm.doc.custom_travel_request)) {
            frappe.msgprint(__("Lengkapi Travel Request terlebih dahulu."));
            return;
          }

          frm.clear_table("expenses");
          frm.clear_table("advances");
          show_expense_selector(frm);
        });
    }
  },
  async custom_get_travel_request_expense(frm) {
    if (!(frm.doc.employee)) {
      frappe.msgprint(__("Lengkapi Employee terlebih dahulu."));
      return;
    }
    if (!(frm.doc.custom_travel_request)) {
      frappe.msgprint(__("Lengkapi Travel Request terlebih dahulu."));
      return;
    }

    frm.clear_table("expenses");
    frm.clear_table("advances");
    show_expense_selector(frm);
  },
  employee(frm) {
    frm.set_query("custom_travel_request", function () {
      return {
        filters: {
          employee: frm.doc.employee
        }
      }
    });
  }
});

frappe.ui.form.on("Expense Claim Detail", {
  async amount(frm, cdt, cdn) {
    let row = locals[cdt][cdn];

    calculate_selisih_detail(frm, cdt, cdn);
    if (row.custom_is_auto_fill) {
      const costing = await frappe.call({
        method: "sth.overrides.expense_claim.get_travel_request_costing",
        args: {
          costing_name: row.costing_expense
        },
      });
      console.log(row, costing.message);
      if (row.amount > costing.message.total_amount) {
        frappe.msgprint(__("Amount tidak boleh lebih besar dari sanction amount."));
        frappe.model.set_value(cdt, cdn, "amount", costing.message.total_amount);
        frappe.model.set_value(cdt, cdn, "sanctioned_amount", costing.message.total_amount);
        return;
      }
    }
  },
  sanctioned_amount(frm, cdt, cdn) {
    calculate_selisih_detail(frm, cdt, cdn);
  },
  expenses_add(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    frappe.model.set_value(cdt, cdn, "custom_travel_request", frm.doc.custom_travel_request);
  }
});

function calculate_selisih_detail(frm, cdt, cdn) {
  let row = locals[cdt][cdn];
  const selisih_field = row.sanctioned_amount < row.amount ? "kurang_bayar" : "lebih_bayar";

  frappe.model.set_value(cdt, cdn, "kurang_bayar", null);
  frappe.model.set_value(cdt, cdn, "lebih_bayar", null);

  if (row.amount != row.sanctioned_amount) {
    frappe.model.set_value(cdt, cdn, selisih_field, Math.abs(row.amount - row.sanctioned_amount));
  }
}

async function show_expense_selector(frm) {
  const fields = [
    {
      fieldtype: 'Link',
      fieldname: 'custom_travel_request',
      label: 'Travel Request',
      in_list_view: true
    },
    {
      fieldtype: 'Link',
      fieldname: 'costing_expense',
      label: 'Costing Expense',
      hidden: true
    },
    {
      fieldtype: 'Date',
      fieldname: 'expense_date',
      label: 'Expense Date',
      in_list_view: true
    },
    {
      fieldtype: 'Date',
      fieldname: 'custom_estimate_depart_date',
      label: 'Estimate Depart Date',
      in_list_view: true
    },
    {
      fieldtype: 'Date',
      fieldname: 'custom_estimate_arrival_date',
      label: 'Estimate Arrival Date',
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

      const updated_items = selected_items.map(item => ({
        ...item,
        custom_is_auto_fill: 1
      }));

      for (const exp of updated_items) {
        frm.add_child("expenses", {
          custom_travel_request: exp.custom_travel_request,
          expense_date: exp.expense_date,
          costing_expense: exp.costing_expense,
          custom_estimate_depart_date: exp.custom_estimate_depart_date,
          custom_estimate_arrival_date: exp.custom_estimate_arrival_date,
          expense_type: exp.expense_type,
          default_account: exp.default_account,
          amount: exp.amount,
          sanctioned_amount: exp.sanctioned_amount,
          custom_is_auto_fill: exp.custom_is_auto_fill,
        })
      }

      frm.refresh_field("expenses");
      d.hide();
    }
  });

  const response = await frappe.call({
    method: "sth.overrides.expense_claim.get_travel_request_expenses",
    args: {
      travel_request: frm.doc.custom_travel_request,
      company: frm.doc.company,
    },
  });
  const travel_request = await frappe.db.get_doc("Travel Request", frm.doc.custom_travel_request)
  const employee_advance = await frappe.db.get_doc("Employee Advance", travel_request.custom_employee_advance);

  frm.add_child("advances", {
    employee_advance: employee_advance.name,
    posting_date: employee_advance.posting_date,
    posting_date: employee_advance.posting_date,
    advance_paid: employee_advance.advance_amount,
    unclaimed_amount: employee_advance.advance_amount,
    allocated_amount: employee_advance.advance_amount,
    advance_account: employee_advance.advance_account,
  })
  frm.refresh_field("advances");

  if (response.message) {
    d.fields_dict.expenses.df.data = response.message;
    d.fields_dict.expenses.refresh();
  }
  d.show();
}