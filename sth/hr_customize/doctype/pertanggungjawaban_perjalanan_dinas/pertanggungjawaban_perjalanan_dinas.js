// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pertanggungjawaban Perjalanan Dinas", {
  no_spd(frm) {
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
