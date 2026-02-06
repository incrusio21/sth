// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pertanggungjawaban Perjalanan Dinas", {
  refresh(frm) {
    if (frm.doc.docstatus === 0 || frm.is_new()) {
      frm.set_query("no_spd", function () {
        return {
          filters: {
            custom_employee_advance: ["is", "set"]
          }
        };
      });
      fetchAccount(frm);
    }
  },
  no_spd(frm) {
    // frm.call("get_data_perjalanan_dinas", { throw_if_missing: true })
    //   .then(r => {
    //     if (r.message) {
    //       let linked_doc = r.message;
    //     }
    //   });
    frm.disable_save();
    frappe.show_alert({
      message: __("please wait..."),
      indicator: "blue"
    }, 5);

    frappe.call({
      doc: frm.doc,
      method: 'get_data_perjalanan_dinas',
      freeze: true,
      freeze_message: __('Fetching perjalanan dinas data...'),
      callback: function (r) {
        frm.enable_save();
        frm.refresh_fields();
        frm.dirty();
      },
      error: function () {
        frm.enable_save();
        frappe.show_alert({
          message: __('Error load perjalanan dinas'),
          indicator: 'red'
        }, 5);
      }
    });
  }
});

frappe.ui.form.on("PPD Costing Detail", {
  sanctioned_amount(frm, cdt, cdn) {
    calculate_realisasi_and_disetujui(frm, cdt, cdn);
  },
  jumlah_verifikasi_hrd(frm, cdt, cdn) {
    calculate_realisasi_and_disetujui(frm, cdt, cdn);
  },
});

function calculate_realisasi_and_disetujui(frm, cdt, cdn) {
  total_realisasi = frm.doc.costings.reduce((sum, { sanctioned_amount = 0 }) => sum + sanctioned_amount, 0);
  total_disetujui = frm.doc.costings.reduce((sum, { jumlah_verifikasi_hrd = 0 }) => sum + jumlah_verifikasi_hrd, 0);

  frm.set_value("total_claimed_amount", total_realisasi);
  frm.set_value("total_sanctioned_amount", total_disetujui);

  frm.refresh_field("total_claimed_amount");
  frm.refresh_field("total_sanctioned_amount");
}

async function fetchAccount(frm) {
  const company = await frappe.db.get_doc("Company", frm.doc.company);

  if (company) {
    frm.set_value("salary_account", company.default_ppd_salary_account);
    frm.set_value("credit_to", company.default_ppd_credit_account);
  }
}

sth.plantation.PertanggungjawabanPerjalananDinas = class PertanggungjawabanPerjalananDinas extends sth.plantation.AccountsController {
  refresh() {
    this.show_general_ledger()
  }
}

cur_frm.script_manager.make(sth.plantation.PertanggungjawabanPerjalananDinas);