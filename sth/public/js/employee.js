frappe.ui.form.on("Employee", {
  setup(frm) {
    frm.set_query("divisi", function () {
      return {
        filters: {
          unit: frm.doc.unit
        }
      }
    })
  },
  refresh(frm) {
    if (!frm.doc.unit) {
      frm.set_df_property("stasiun", "hidden", 1);
      frm.set_df_property("coa_stasiun", "hidden", 1);

<<<<<<< Updated upstream
  stasiun(frm) {
    set_coa_stasiun(frm);
  },

  company(frm) {
    if (frm.doc.stasiun) {
      set_coa_stasiun(frm);
    }
  },

=======
      return;
    }

    frappe.db.get_doc("Unit", frm.doc.unit).then(doc => {
      frm.set_df_property("stasiun", "hidden", !doc.mill);
      frm.set_df_property("coa_stasiun", "hidden", !doc.mill);
    });
  },
  unit(frm) {
    if (!frm.doc.unit) {
      frm.set_df_property("stasiun", "hidden", 1);
      frm.set_df_property("coa_stasiun", "hidden", 1);

      return;
    }

    frappe.db.get_doc("Unit", frm.doc.unit).then(doc => {
      frm.set_df_property("stasiun", "hidden", !doc.mill);
      frm.set_df_property("coa_stasiun", "hidden", !doc.mill);

      frm.set_query("stasiun", function () {
        return {
          query: "sth.custom.employee.get_stasiun_by_unit",
          filters: {
            unit: frm.doc.unit
          }
        };
      });
    });
  },
  stasiun(frm) {
    frm.set_query("coa_stasiun", function () {
      return {
        query: "sth.custom.employee.get_account_by_station_and_company",
        filters: {
          station: frm.doc.stasiun,
          company: frm.doc.company,
        }
      };
    });
  },
>>>>>>> Stashed changes
  date_of_joining(frm) {
    if (frm.doc.date_of_joining) {
      frm.set_value("custom_employment_tenure", getMonthDifference(frm.doc.date_of_joining));
    }
  }
});

// COA Stasiun diambil dari tabel Station Procurement Settings milik stasiun,
// barisnya dipilih berdasarkan company karyawan.
function set_coa_stasiun(frm) {
  if (!frm.doc.stasiun) {
    frm.set_value("coa_stasiun", null);
    return;
  }

  frappe.call({
    method: "frappe.client.get",
    args: { doctype: "Station Master", name: frm.doc.stasiun },
    callback(r) {
      if (!r.message) return;

      const settings = r.message.station_procurement_settings || [];
      const row = settings.find((s) => s.company === frm.doc.company);

      frm.set_value("coa_stasiun", (row && row.account) || null);

      if (!row) {
        frappe.show_alert({
          message: __("Stasiun {0} belum punya akun untuk company {1} di Station Procurement Settings.", [
            frm.doc.stasiun,
            frm.doc.company
          ]),
          indicator: "orange"
        });
      }
    }
  });
}

function getMonthDifference(dateString) {
  const inputDate = new Date(dateString);
  const now = new Date();

  let years = now.getFullYear() - inputDate.getFullYear();
  let months = now.getMonth() - inputDate.getMonth();

  let totalMonths = years * 12 + months;

  if (now.getDate() < inputDate.getDate()) {
    totalMonths -= 1;
  }

  tahun = Math.floor(totalMonths / 12)
  bulan = totalMonths % 12

  return `${tahun} Tahun ${bulan} Bulan`;
}