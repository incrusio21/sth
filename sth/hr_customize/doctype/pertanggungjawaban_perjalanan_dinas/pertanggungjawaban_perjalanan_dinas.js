// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

// Tampilan link title (title field) dimatikan selama berada di Pertanggungjawaban
// Perjalanan Dinas, supaya field link menampilkan nama dokumen aslinya.
// frappe.utils bersifat global dan desk tidak reload saat pindah menu, jadi fungsi
// aslinya disimpan lalu dikembalikan begitu route keluar dari doctype ini.
const PPD_DOCTYPE = "Pertanggungjawaban Perjalanan Dinas";
// Kosongkan untuk semua doctype, atau isi mis. ["Travel Request"] untuk membatasi.
const PPD_HIDE_LINK_TITLE_FOR = [];

let ppd_original_link_title = null;

function ppd_is_link_title_hidden(doctype) {
  return !PPD_HIDE_LINK_TITLE_FOR.length || PPD_HIDE_LINK_TITLE_FOR.includes(doctype);
}

function ppd_hide_link_title() {
  if (ppd_original_link_title) return;

  ppd_original_link_title = {
    get: frappe.utils.get_link_title,
    fetch: frappe.utils.fetch_link_title
  };

  // Mengembalikan name apa adanya; formatter Link menganggapnya "tanpa title".
  frappe.utils.get_link_title = function (doctype, name) {
    if (ppd_is_link_title_hidden(doctype)) return name;
    return ppd_original_link_title.get.apply(this, arguments);
  };

  frappe.utils.fetch_link_title = function (doctype, name) {
    if (ppd_is_link_title_hidden(doctype)) return Promise.resolve(name);
    return ppd_original_link_title.fetch.apply(this, arguments);
  };
}

function ppd_restore_link_title() {
  if (!ppd_original_link_title) return;

  frappe.utils.get_link_title = ppd_original_link_title.get;
  frappe.utils.fetch_link_title = ppd_original_link_title.fetch;
  ppd_original_link_title = null;
}

function ppd_sync_link_title() {
  const route = frappe.get_route() || [];
  if (route[1] === PPD_DOCTYPE) {
    ppd_hide_link_title();
  } else {
    ppd_restore_link_title();
  }
}

if (!frappe.__ppd_link_title_watcher) {
  frappe.__ppd_link_title_watcher = true;
  frappe.router.on("change", ppd_sync_link_title);
}

frappe.ui.form.on("Pertanggungjawaban Perjalanan Dinas", {
  onload(frm) {
    // dipanggil sebelum field dirender, supaya link tidak sempat tampil sebagai title
    ppd_sync_link_title();
  },
  refresh(frm) {
    ppd_sync_link_title();

    if (frm.doc.docstatus === 0 || frm.is_new()) {
      frm.set_query("no_spd", function () {
        return {
          filters: {
            custom_employee_advance: ["is", "set"]
          }
        };
      });
      frm.set_query("no_pdo", function () {
        return {
          filters: {
            docstatus: 1,
            grand_total_perjalanan_dinas: [">", 0]
          }
        };
      });
      if (frm.doc.sumber_pertanggungjawaban !== "PDO") {
        fetchAccount(frm);
      }
    }

    frm.fields_dict["costings"].grid.update_docfield_property(
      "jumlah_verifikasi_hrd",
      "read_only",
      0
    );

    if (frm.is_new() && frm.is_new() != undefined) {
      // console.log("render is_new");
      frm.fields_dict["costings"].grid.update_docfield_property(
        "jumlah_verifikasi_hrd",
        "read_only",
        1
      );
    }

    if (frm.doc.__islocal && !["Butuh Persetujuan 1", "Butuh Persetujuan 2"].includes(frm.doc.workflow_state)) {
      // console.log("render workflow_state");
      frm.fields_dict["costings"].grid.update_docfield_property(
        "jumlah_verifikasi_hrd",
        "read_only",
        1
      );
    }

    // console.log(frm.doc.__islocal, frm.doc.workflow_state);
    frm.refresh_field("costings");
    createPayment(frm);
  },
  sumber_pertanggungjawaban(frm) {
    frm.set_value("no_spd", null);
    frm.set_value("no_pdo", null);
    frm.clear_table("costings");
    frm.clear_table("itinerary");
    frm.clear_table("guests");
    frm.set_value("total_claimed_amount", 0);
    frm.set_value("total_sanctioned_amount", 0);
    frm.set_value("total_down_amount", 0);
    frm.refresh_fields();
  },
  no_spd(frm) {
    if (!frm.doc.no_spd) return;
    fetch_perjalanan_dinas(frm);
  },
  no_pdo(frm) {
    if (!frm.doc.no_pdo) return;
    fetch_perjalanan_dinas(frm);
  }
});

function fetch_perjalanan_dinas(frm) {
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

frappe.ui.form.on("PPD Costing Detail", {
  sanctioned_amount(frm, cdt, cdn) {
    calculate_realisasi_and_disetujui(frm, cdt, cdn);
  },
  jumlah_verifikasi_hrd(frm, cdt, cdn) {
    calculate_realisasi_and_disetujui(frm, cdt, cdn);
  },
});

function createPayment(frm) {
  // Sumber PDO tidak dibayar dari sini, potongannya diambil saat Realisasi PDO
  if (frm.doc.sumber_pertanggungjawaban == "PDO") return;

  if (
    frm.doc.docstatus == 1 &&
    frm.doc.outstanding_amount > 0 &&
    !frm.doc.payment_voucher
  ) {
    if (frm.doc.status_selisih == "Tidak Ada Selisih") {
      frappe.show_alert({
        message: __('Tidak Ada Selisih'),
        indicator: 'red'
      }, 5);
      return;
    }

    frm.add_custom_button('Payment', () => {
      frappe.model.open_mapped_doc({
        method: "sth.hr_customize.doctype.pertanggungjawaban_perjalanan_dinas.pertanggungjawaban_perjalanan_dinas.make_payment_entry",
        frm: frm,
      });
    }, 'Create');
  }
}

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

function filter_jenis_ex_type(frm) {
  frm.set_query('expense_type', 'costings', () => {
    return {
      filters: {
        is_hrd: 1
      }
    }
  });
}