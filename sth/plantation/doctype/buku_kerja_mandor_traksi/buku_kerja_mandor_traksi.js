// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

sth.plantation.setup_budget_controller()

frappe.ui.form.on("Buku Kerja Mandor Traksi", {
  refresh(frm) {
    // frm.toggle_display("kendaraan_pengganti", frm.doc.is_kendaraan_pengganti)
    // frm.set_df_property("kdr", "read_only", frm.doc.is_kendaraan_pengganti)

    // frm.toggle_display("operator_supir_pengganti", frm.doc.is_operator_supir_pengganti)
    // frm.set_df_property("nk", "read_only", frm.doc.is_operator_supir_pengganti)

    if (frm.is_new()) {
      frm.toggle_display("blok", false);
      frm.toggle_display("batch", false);
    } else {
      frappe.db.get_doc("Kegiatan", frm.doc.kegiatan).then(r => {
        if (r.is_bibitan) {
          frm.toggle_display("batch", true);
          frm.toggle_display("blok", false);
        } else {
          frm.toggle_display("batch", false);
          frm.toggle_display("blok", true);
        }
      });
    }

    frappe.call({
      method: "get_employee_supervisi",
      doc: frm.doc,
      callback: function (r) {
        if (r.message) {
          let employee = r.message.map(row => row.name);
          frm.set_query("mdr", function () {
            return {
              filters: [["Employee", "name", "in", employee]]
            };
          });
        }
      }
    })

    frappe.call({
      method: "get_employee_traksi",
      doc: frm.doc,
      callback: function (r) {
        if (r.message) {
          let employee = r.message.map(row => row.name);
          frm.set_query("nk", function () {
            return {
              filters: [["Employee", "name", "in", employee]]
            };
          });
        }
      }
    })

    frappe.db.get_value("Company",
      { name: frm.doc.company },
      ["name", "custom_ump_harian"]
    ).then(r => {
      if (!r.message) return
      frm.set_value("uph", r.message.custom_ump_harian)
    })
  },
  // is_kendaraan_pengganti(frm) {
  //   frm.toggle_display("kendaraan_pengganti", frm.doc.is_kendaraan_pengganti)
  //   frm.set_df_property("kdr", "read_only", frm.doc.is_kendaraan_pengganti)
  // },
  // is_operator_supir_pengganti(frm) {
  //   frm.toggle_display("operator_supir_pengganti", frm.doc.is_operator_supir_pengganti)
  //   frm.set_df_property("nk", "read_only", frm.doc.is_operator_supir_pengganti)

  //   if (frm.doc.is_operator_supir_pengganti) {
  //     frappe.call({
  //       method: "get_employee_traksi",
  //       doc: frm.doc,
  //       callback: function (r) {
  //         if (r.message) {
  //           let employee = r.message.map(row => row.name);
  //           frm.set_query("operator_supir_pengganti", function () {
  //             return {
  //               filters: [["Employee", "name", "in", employee]]
  //             };
  //           });
  //         }
  //       }
  //     })
  //   }
  // },
  tgl_trk(frm) {
    frappe.db.get_value("Rencana Kerja Harian",
      { posting_date: frm.doc.tgl_trk },
      ["name"]
    ).then(r => {
      if (Object.keys(r.message).length === 0) {
        // frappe.throw("Rencana Kerja Harian Tidak Ditemukan!")
        return
      }

      frappe.db.get_doc("Rencana Kerja Harian", r.message.name)
        .then(doc => {
          const rkh_kendaraan = doc.kendaraan.map(r => r.item_pengganti || r.item)

          frm.set_query("kdr", function () {
            return {
              filters: [
                ["Alat Berat Dan Kendaraan", "name", "in", rkh_kendaraan]
              ]
            };
          });

          console.log(rkh_kendaraan);
        });
    });
  },
  company(frm) {
    frm.set_query("unit", function () {
      return {
        filters: [
          ["Unit", "company", "=", frm.doc.company]
        ]
      };
    });
  },
  unit(frm) {
    frm.set_query("kendaraan_pengganti", function () {
      return {
        filters: [
          ["Alat Berat Dan Kendaraan", "unit", "=", frm.doc.unit]
        ]
      };
    });
    frm.set_query("blok", function () {
      return {
        filters: [
          ["Blok", "unit", "=", frm.doc.unit]
        ]
      };
    });
  },
  mdr(frm) {
    if (frm.doc.mdr) {
      frappe.db.get_value("Employee", frm.doc.mdr, "designation", function (r) {
        if (r && r.designation) {
          // ambil nama jabatannya (bukan kode)
          frappe.db.get_value("Designation", r.designation, "designation_name", function (res) {
            if (res && res.designation_name) {
              frm.set_value("designation", res.designation_name);
            }
          });
        }
      });
    } else {
      frm.set_value("designation", "");
    }
  },
  nk(frm) {
    if (frm.doc.nk) {
      frappe.db.get_value("Employee", frm.doc.nk, "designation", function (r) {
        if (r && r.designation) {
          // ambil nama jabatannya (bukan kode)
          frappe.db.get_value("Designation", r.designation, "designation_name", function (res) {
            if (res && res.designation_name) {
              frm.set_value("jbtn", res.designation_name);
            }
          });
        }
      });
    } else {
      frm.set_value("jbtn", "");
    }
  },
  // kendaraan_pengganti(frm) {
  //   frappe.db.get_doc("Alat Berat Dan Kendaraan", frm.doc.kendaraan_pengganti)
  //     .then(doc => {
  //       frm.set_value('jk', doc.tipe_master);
  //     })
  // },
  tipe_master_kendaraan(frm) {
    if (frm.doc.tipe_master_kendaraan) {
      frm.set_query("kdr", function () {
        return {
          filters: [
            ["Alat Berat Dan Kendaraan", "tipe_master", "=", frm.doc.tipe_master_kendaraan]
          ]
        };
      });
    } else {
      frm.set_query("kdr", function () {
        return {};
      });
    }
    // if (frm.doc.tgl_trk == undefined) {
    //   frappe.throw("Tanggal Transaksi Harap Diisi!")
    //   return
    // }

    // frappe.db.get_value("Rencana Kerja Harian",
    //   { posting_date: frm.doc.tgl_trk },
    //   ["name"]
    // ).then(r => {
    //   if (Object.keys(r.message).length === 0) {
    //     // frappe.throw("Rencana Kerja Harian Tidak Ditemukan!")
    //     return
    //   }

    //   frappe.db.get_doc("Rencana Kerja Harian", r.message.name)
    //     .then(doc => {
    //       const rkh_kendaraan = doc.kendaraan.map(r => r.item_pengganti || r.item)

    //       frm.set_query("kdr", function () {
    //         return {
    //           filters: [
    //             ["Alat Berat Dan Kendaraan", "name", "in", rkh_kendaraan],
    //             ["Alat Berat Dan Kendaraan", "tipe_master", "=", frm.doc.tipe_master_kendaraan]
    //           ]
    //         };
    //       });

    //       console.log(rkh_kendaraan);
    //     });
    // });
  },
  kdr(frm) {
    if (frm.doc.kdr) {
      frappe.db.get_value("Alat Berat Dan Kendaraan", frm.doc.kdr, "operator")
        .then(r => {
          if (r.message) {
            frm.set_value("nk", r.message.operator);
          }
        });
    } else {
      frm.set_value("nk", "");
    }
  },
  kegiatan(frm) {
    frappe.db.get_doc("Kegiatan", frm.doc.kegiatan).then(r => {
      if (r.is_bibitan) {
        frm.toggle_display("batch", true);
        frm.toggle_display("blok", false);
      } else {
        frm.toggle_display("batch", false);
        frm.toggle_display("blok", true);
      }
    });
  },
  hk(frm) {
    frappe.call({
      method: "get_min_basis_premi_and_rupiah_premi_kegiatan",
      doc: frm.doc,
      args: {
        kegiatan: frm.doc.kegiatan,
        company: frm.doc.company,
      },
      callback: function (r) {
        if (!r.message) return;

        console.log(r.message, frm.doc.hk)
        if (frm.doc.hk >= r.message.min_basis_premi) {
          frm.set_value("rupiah_premi", r.message.rupiah_premi);
        }

        const pekerjaan_subtotal = (frm.doc.hk * frm.doc.rupiah_basis) + frm.doc.rupiah_premi
        const subtotal_upah = (frm.doc.hk * frm.doc.rupiah_basis)

        if (frm.doc.jk == "Dump Truck") {
          frm.set_value("subtotal_upah", subtotal_upah)
          frm.set_value("pekerjaan_subtotal", pekerjaan_subtotal)
        }
      }
    })

    frappe.call({
      method: "get_volume_basis_kegiatan",
      doc: frm.doc,
      args: {
        kegiatan: frm.doc.kegiatan,
        company: frm.doc.company,
      },
      callback: function (r) {
        if (r.message) {
          if (frm.doc.jk == "Dump Truck") {
            hari_kerja = (frm.doc.hk / r.message) > 1 ? 1 : parseFloat((frm.doc.hk / r.message).toFixed(2));
            frm.set_value("hari_kerja", hari_kerja)
          } else {
            frm.set_value("hari_kerja", 1)
          }
        }
      }
    })
  },
  rupiah_premi(frm) {
    const pekerjaan_subtotal = (frm.doc.hk * frm.doc.rupiah_basis) + frm.doc.rupiah_premi

    if (frm.doc.jk == "Dump Truck") {
      frm.set_value("pekerjaan_subtotal", pekerjaan_subtotal)
    }
  },
  premi(frm) {
    if (frm.doc.jk != "Dump Truck" && frm.doc.uph != 0) {
      const operator_subtotal = frm.doc.uph + frm.doc.premi
      console.log({
        "operator_subtotal": operator_subtotal,
        "uph": frm.doc.uph,
        "premi": frm.doc.premi
      })
      frm.set_value("operator_subtotal", operator_subtotal)
    }
  }
});

sth.plantation.BukuKerjaMandorTraksi = class BukuKerjaMandorTraksi extends sth.plantation.BudgetController {
  setup(doc) {
    super.setup(doc)
    this.kegiatan_fetch_fieldname = ["rupiah_basis"]
  }
  set_query_field() { }
  company(doc) { }
}

cur_frm.script_manager.make(sth.plantation.BukuKerjaMandorTraksi);