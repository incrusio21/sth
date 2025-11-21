// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Transaksi THR", {
  refresh(frm) {
    if (frm.doc.docstatus === 0 || frm.is_new()) {
      cur_frm.toggle_display("get_employee_data", true);
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

      frm.doc.table_employee.forEach(r => {
        const rule_map = [
          { key: "UMR", fields: ["umr"] },
          { key: "GP", fields: ["gaji_pokok"] },
          { key: "Uang_Daging", fields: ["uang_daging"] },
          { key: "Natura", fields: ["natura"] },
          {
            key: "Jumlah_Bulan_Bekerja",
            fields: ["jumlah_bulan_bekerja", "masa_kerja"]
          },
        ];

        rule_map.forEach(item => {
          item.fields.forEach(f => {
            if (r[f] == 0 || r[f] == undefined || r[f] == null) {
              r[f] = null;
            }
            console.log(`${Math.random()} - ${f} - ${r[f]}`)
          });
        });

        frm.refresh_field("table_employee");
      });
    }

    frm.set_df_property("table_employee", "cannot_add_rows", true);
  },
  make_payment_entry: function (frm) {
    let method = "sth.hr_customize.doctype.transaksi_thr.transaksi_thr.get_payment_entry";
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

    frm.clear_table("table_employee");

    let filters = {
      company: frm.doc.company,
      custom_unit: frm.doc.unit,
    };

    if (frm.doc.religion_group) {
      filters.custom_religion_group = frm.doc.religion_group
    }

    if (frm.doc.employee_grade) {
      filters.grade = frm.doc.employee_grade;
    }

    if (frm.doc.employment_type) {
      filters.employment_type = frm.doc.employment_type;
    }

    if (frm.doc.kriteria) {
      filters.custom_kriteria = frm.doc.kriteria;
    }

    if (frm.doc.religion_group) {
      filters.custom_religion_group = frm.doc.religion_group;
    }

    const records = await frappe.call({
      method: "get_all_employee",
      doc: frm.doc,
      args: {
        filters: filters
      },
    });

    if (!records?.message.length) {
      frappe.msgprint(__("Tidak ada data karyawan yang ditemukan."));
      return;
    }

    for (const emp of records.message) {
      const thr_rate = await frappe.call({
        method: "get_thr_rate",
        doc: frm.doc,
        args: {
          employee: emp.name,
          pkp_status: emp.pkp_status,
          employee_grade: emp.grade,
          employment_type: emp.employment_type,
          kriteria: emp.custom_kriteria
        },
      });

      if (thr_rate.message.thr_rule) {
        let row = frm.add_child("table_employee", {
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
          thr_rule: thr_rate.message.thr_rule,
          subtotal: thr_rate.message.subtotal,
        });

        const rule_map = [
          { key: "UMR", fields: ["umr"] },
          { key: "GP", fields: ["gaji_pokok"] },
          { key: "Uang_Daging", fields: ["uang_daging"] },
          { key: "Natura", fields: ["natura"] },
          {
            key: "Jumlah_Bulan_Bekerja",
            fields: ["jumlah_bulan_bekerja", "masa_kerja"]
          },
        ];

        if (row.thr_rule) {
          rule_map.forEach(item => {
            if (row.thr_rule.includes(item.key)) {
              item.fields.forEach(f => {
                row[f] = thr_rate.message[f] ?? null;
              });
            } else {
              item.fields.forEach(f => {
                row[f] = null;
              });
            }
          });
        }

      }
    }

    // for (const emp of records.message) {
    //   const thr_rate = await frappe.call({
    //     method: "get_thr_rate",
    //     doc: frm.doc,
    //     args: {
    //       employee: emp.name,
    //       pkp_status: emp.pkp_status,
    //       employee_grade: emp.grade,
    //       employment_type: emp.employment_type,
    //       kriteria: emp.custom_kriteria
    //     },
    //   });

    //   if (thr_rate.message) {
    //     let row = frm.add_child("table_employee", {
    //       nik: emp.no_ktp,
    //       employee: emp.name,
    //       employee_name: emp.employee_name,
    //       date_of_joining: emp.date_of_joining,
    //       employee_grade: emp.grade,
    //       employment_type: emp.employment_type,
    //       custom_kriteria: emp.custom_kriteria,
    //       bank_ac_no: emp.bank_ac_no,
    //       bank_name: emp.bank_name,
    //       designation: emp.designation,
    //       custom_divisi: emp.custom_divisi,
    //       custom_kriteria: emp.custom_kriteria,
    //       thr_rule: thr_rate.message.thr_rule,
    //       subtotal: thr_rate.message.subtotal,
    //     });

    //     frm.doc.table_employee.forEach(r => {
    //       const rule_map = [
    //         { key: "UMR", fields: ["umr"] },
    //         { key: "GP", fields: ["gaji_pokok"] },
    //         { key: "Uang_Daging", fields: ["uang_daging"] },
    //         { key: "Natura", fields: ["natura"] },
    //         {
    //           key: "Jumlah_Bulan_Bekerja",
    //           fields: ["jumlah_bulan_bekerja", "masa_kerja"]
    //         },
    //       ];

    //       if (r.thr_rule) {
    //         rule_map.forEach(item => {
    //           if (r.thr_rule.includes(item.key)) {
    //             item.fields.forEach(f => {
    //               console.log(emp.employee_name, f, thr_rate.message[f], thr_rate.message);
    //               r[f] = thr_rate.message[f]
    //             });
    //           } else {
    //             item.fields.forEach(f => {
    //               r[f] = null
    //             });
    //           }
    //         });
    //       } else {
    //         r.gaji_pokok = null;
    //         r.umr = null;
    //         r.uang_daging = null;
    //         r.natura = null;
    //         r.masa_kerja = null;
    //         r.jumlah_bulan_bekerja = null;
    //       }
    //     });
    //   }

    //   frm.refresh_field("table_employee");
    // }
    frm.refresh_field("table_employee");

    frm.doc.table_employee.forEach(r => {
      const rule_map = [
        { key: "UMR", fields: ["umr"] },
        { key: "GP", fields: ["gaji_pokok"] },
        { key: "Uang_Daging", fields: ["uang_daging"] },
        { key: "Natura", fields: ["natura"] },
        {
          key: "Jumlah_Bulan_Bekerja",
          fields: ["jumlah_bulan_bekerja", "masa_kerja"]
        },
      ];

      rule_map.forEach(item => {
        item.fields.forEach(f => {
          if (r[f] == 0 || r[f] == undefined || r[f] == null) {
            r[f] = null;
          }
          console.log(`${Math.random()} - ${f} - ${r[f]}`)
        });
      });

      frm.refresh_field("table_employee");
    });
  },
});

function toggle_thr_fields(frm, rule) {
  const grid = frm.fields_dict.table_employee.grid;

  const all_fields = [
    "gaji_pokok",
    "umr",
    "uang_daging",
    "natura",
    "masa_kerja",
    "jumlah_bulan_bekerja"
  ];

  // Hide semua field dulu
  all_fields.forEach(f => grid.update_docfield_property(f, "hidden", 1));

  const rule_map = [
    { key: "UMR", fields: ["umr"] },
    { key: "GP", fields: ["gaji_pokok"] },
    { key: "Uang_Daging", fields: ["uang_daging"] },
    { key: "Natura", fields: ["natura"] },
    {
      key: "Jumlah_Bulan_Bekerja",
      fields: ["jumlah_bulan_bekerja", "masa_kerja"]
    },
  ];

  // Show berdasarkan rule
  rule_map.forEach(item => {
    // console.log({
    //   id: Math.random(),
    //   rule: rule,
    //   key: item.key,
    //   is_show: rule.includes(item.key)
    // });
    if (rule.includes(item.key)) {
      // console.log({
      //   message: "END",
      //   fields: item.fields
      // });
      item.fields.forEach(f => {
        grid.update_docfield_property(f, "hidden", 0);
      });
    }
  });

  grid.refresh();
}

sth.plantation.TransaksiTHR = class TransaksiTHR extends sth.plantation.AccountsController {
  refresh() {
    this.show_general_ledger()
  }
}

cur_frm.script_manager.make(sth.plantation.TransaksiTHR);