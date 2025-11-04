// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Transaksi THR", {
  refresh(frm) {
    if (frm.doc.docstatus === 0 && frm.is_new()) {
      cur_frm.toggle_display("get_employee_data", true);
    } else {
      cur_frm.toggle_display("get_employee_data", false);
    }

    frm.set_df_property("table_employee", "cannot_add_rows", true);
  },
  async unit(frm) {
    const result = await frappe.db.get_value("Setup THR", {
      unit: frm.doc.unit,
      company: frm.doc.company,
    }, ["name"]);

    if (result?.message?.name) {
      frm.set_value("setup_thr", result.message.name);
    }
  },
  async get_employee_data(frm) {
    if (!(frm.doc.unit && frm.doc.company && frm.doc.setup_thr)) {
      frappe.msgprint(__("Lengkapi Unit, Company, Setup THR terlebih dahulu."));
      return;
    }

    const company = await frappe.db.get_value("Company", frm.doc.company, ["custom_uang_daging"]);
    const records = await frappe.db.get_list("Employee", {
      filters: {
        custom_unit: frm.doc.unit,
        company: frm.doc.company,
      },
      fields: [
        "no_ktp",
        "name",
        "employee_name",
        "date_of_joining",
        "grade",
        "employment_type",
        "custom_kriteria",
        "bank_ac_no",
        "bank_name",
        "designation",
        "custom_divisi",
        "custom_kriteria",
      ],
    });

    if (!records?.length) {
      frappe.msgprint(__("Tidak ada data karyawan yang ditemukan."));
      return;
    }

    frm.clear_table("table_employee");

    for (const emp of records) {
      const response = await frappe.call({
        method: "get_salary_structure_assignment",
        doc: frm.doc,
        args: {
          employee: emp.name,
        },
      });

      if (!response.message) {
        frappe.msgprint(__("Employee tidak memiliki Salary Structure Assignment."));
        console.log(response.message);
        return;
      }
      frm.add_child("table_employee", {
        nik: emp.no_ktp,
        employee: emp.name,
        employee_name: emp.employee_name,
        date_of_joining: emp.date_of_joining,
        employee_grade: emp.grade,
        employment_type: emp.employment_type,
        custom_kriteria: emp.custom_kriteria,
        bank_ac_no: emp.bank_ac_no,
        bank_name: emp.bank_name,
        designation: emp.designation,
        custom_divisi: emp.custom_divisi,
        custom_kriteria: emp.custom_kriteria,
        uang_daging: company.message.custom_uang_daging ?? 0,
      });
    }

    frm.refresh_field("table_employee");
  }
});
