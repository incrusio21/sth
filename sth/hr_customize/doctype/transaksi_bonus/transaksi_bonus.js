// Copyright (c) 2025, DAS
// For license information, please see license.txt

frappe.ui.form.on("Transaksi Bonus", {
  async refresh(frm) {
    if (frm.doc.docstatus === 0 || frm.is_new()) {
      cur_frm.toggle_display("get_employee_data", true);
      fetchAccountAndSalaryAccount(frm);
    } else {
      cur_frm.toggle_display("get_employee_data", false);
    }

    if (frm.doc.docstatus === 1 && frappe.model.can_create("Payment Entry")) {
      frm.add_custom_button(
        __("Payment"),
        function () {
          frm.events.make_payment_entry(frm);
        },
        __("Create"),
      );
    }

    frm.set_df_property("table_employee", "cannot_add_rows", true);

    if (!frm.is_new() && frm.doc.bp) {
      await frappe.db.get_doc("Setup Bonus", frm.doc.bp).then(r => {
        const kpi_options = r.table_zcyy.map(row => row.kv);

        frm.fields_dict["table_employee"].grid.update_docfield_property(
          "kpi_value",
          "options",
          kpi_options
        );

        frm.fields_dict["table_employee"].grid.refresh();
      });
    }
  },
  make_payment_entry: function (frm) {
    let method = "sth.hr_customize.doctype.transaksi_bonus.transaksi_bonus.get_payment_entry";
    return frappe.call({
      method: method,
      args: {
        dt: frm.doc.doctype,
        dn: frm.doc.name,
      },
      callback: function (r) {
        var doclist = frappe.model.sync(r.message);
        frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
      },
    });
  },
  async get_employee_data(frm) {
    if (!(frm.doc.unit && frm.doc.company && frm.doc.eg && frm.doc.et)) {
      frappe.msgprint(__("Lengkapi Unit, Company, Grade, dan Employment Type terlebih dahulu."));
      return;
    }

    const records = await frappe.db.get_list("Employee", {
      filters: {
        custom_unit: frm.doc.unit,
        company: frm.doc.company,
        grade: frm.doc.eg,
        employment_type: frm.doc.et,
      },
      fields: [
        "name",
        "employee_name",
        "date_of_joining",
        "employment_type",
        "custom_kriteria",
        "bank_ac_no",
      ],
    });

    if (!records?.length) {
      frappe.msgprint(__("Tidak ada data karyawan yang ditemukan."));
      return;
    }

    frm.clear_table("table_employee");

    for (const emp of records) {
      frm.add_child("table_employee", {
        employee: emp.name,
        employee_name: emp.employee_name,
        date_of_joining: emp.date_of_joining,
        employment_type: emp.employment_type,
        custom_kriteria: emp.custom_kriteria,
        bank_ac_no: emp.bank_ac_no,
      });
    }

    if (frm.doc.bp) {
      const setup_bonus = await frappe.db.get_doc("Setup Bonus", frm.doc.bp);
      const kpi_options = setup_bonus.table_zcyy.map(r => r.kv);

      frm.fields_dict["table_employee"].grid.update_docfield_property(
        "kpi_value",
        "options",
        kpi_options
      );
    }

    frm.refresh_field("table_employee");
  },
  async et(frm) {
    const result = await frappe.db.get_value("Setup Bonus", {
      unit: frm.doc.unit,
      company: frm.doc.company,
      eg: frm.doc.eg,
      et: frm.doc.et,
    }, ["name"]);

    if (result?.message?.name) {
      frm.set_value("bp", result.message.name);
    }
  },
});

frappe.ui.form.on("Detail Transaksi Bonus", {
  async kpi_value(frm, cdt, cdn) {
    const row = locals[cdt][cdn];

    const response = await frappe.call({
      method: "calculate_total_bonus",
      doc: frm.doc,
      args: {
        company: frm.doc.company,
        kriteria: row.custom_kriteria,
        employee: row.employee,
        name: frm.doc.bp,
        kpi_value: row.kpi_value,
      },
    });

    if (response.message) {
      const { bonus, setup_bonus } = response.message;
      const total_bonus = bonus.salary * setup_bonus.compensation_value;

      if (bonus.salary == 0) {
        frappe.msgprint(__("Employee tidak memiliki Salary Structure Assignment."));
        return;
      }
      frappe.model.set_value(cdt, cdn, "compensation_value", setup_bonus.compensation_value);
      frappe.model.set_value(cdt, cdn, "salary", bonus.salary);
      frappe.model.set_value(cdt, cdn, "total_bonus", total_bonus);
    }
  },
});

async function fetchAccountAndSalaryAccount(frm) {
  const company = await frappe.db.get_doc("Company", frm.doc.company);
  const salarySettings = await frappe.call({
    method: "frappe.client.get",
    args: {
      doctype: "Bonus and Allowance Settings",
      name: "Bonus and Allowance Settings"
    }
  });

  if (company) {
    frm.set_value("salary_account", company.custom_default_bonus_salary_account);
    frm.set_value("credit_to", company.custom_default_bonus_account);
  }

  if (salarySettings.message) {
    frm.set_value("earning_bonus_component", salarySettings.message.earning_bonus_component);
    frm.set_value("deduction_bonus_component", salarySettings.message.deduction_bonus_component);
  }
}

sth.plantation.TransaksiBonus = class TransaksiBonus extends sth.plantation.AccountsController {
  refresh() {
    this.show_general_ledger()
  }
}

cur_frm.script_manager.make(sth.plantation.TransaksiBonus);