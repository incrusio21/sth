frappe.ui.form.on("Employee", {
  setup(frm) {
    frm.set_query("divisi", function () {
      return {
        filters: {
          unit: frm.doc.unit
        }
      }
    })

    // didaftarkan di setup, bukan hanya di trigger unit, supaya filternya tetap
    // jalan saat form dibuka ulang dengan unit yang sudah terisi
    frm.set_query("stasiun", function () {
      return {
        query: "sth.custom.employee.get_stasiun_by_unit",
        filters: {
          unit: frm.doc.unit
        }
      };
    });

    frm.set_query("coa_stasiun", function () {
      return {
        query: "sth.custom.employee.get_account_by_station_and_company",
        filters: {
          station: frm.doc.stasiun,
          company: frm.doc.company
        }
      };
    });
  },

  refresh(frm) {
    toggle_stasiun_fields(frm);
  },

  unit(frm) {
    toggle_stasiun_fields(frm);
  },

  stasiun(frm) {
    set_coa_stasiun(frm);
  },

  company(frm) {
    if (frm.doc.stasiun) {
      set_coa_stasiun(frm);
    }
  },

  date_of_joining(frm) {
    if (frm.doc.date_of_joining) {
      frm.set_value("custom_employment_tenure", getMonthDifference(frm.doc.date_of_joining));
    }
  }
});

// stasiun hanya relevan untuk unit yang berupa mill
function toggle_stasiun_fields(frm) {
  if (!frm.doc.unit) {
    frm.set_df_property("stasiun", "hidden", 1);
    frm.set_df_property("coa_stasiun", "hidden", 1);

    return;
  }

  frappe.db.get_doc("Unit", frm.doc.unit).then(doc => {
    frm.set_df_property("stasiun", "hidden", !doc.mill);
    frm.set_df_property("coa_stasiun", "hidden", !doc.mill);
  });
}

// COA Stasiun diambil dari akun operasional milik stasiun sesuai company.
// Kalau pilihannya cuma satu langsung diisi, kalau lebih user memilih sendiri
// lewat daftar yang sudah difilter.
function set_coa_stasiun(frm) {
  if (!frm.doc.stasiun) {
    frm.set_value("coa_stasiun", null);
    return;
  }

  frappe.call({
    method: "sth.custom.employee.get_coa_stasiun_options",
    args: {
      station: frm.doc.stasiun,
      company: frm.doc.company
    },
    callback(r) {
      const options = r.message || [];

      if (options.length === 1) {
        frm.set_value("coa_stasiun", options[0]);
        return;
      }

      if (!options.length) {
        frm.set_value("coa_stasiun", null);
        frappe.show_alert({
          message: __("Stasiun {0} belum punya akun operasional untuk company {1}.", [
            frm.doc.stasiun,
            frm.doc.company
          ]),
          indicator: "orange"
        });
        return;
      }

      if (!options.includes(frm.doc.coa_stasiun)) {
        frm.set_value("coa_stasiun", null);
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
