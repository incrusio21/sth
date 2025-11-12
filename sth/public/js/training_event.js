frappe.ui.form.on("Training Event", {
  refresh(frm) {
    // if (frm.doc.docstatus === 1 && frappe.model.can_create("Payment Entry")) {
    //   frm.add_custom_button(
    //     __("Payment"),
    //     function () {
    //       frm.events.make_payment_entry(frm);
    //     },
    //     __("Create"),
    //   );
    // }
    if (frm.doc.docstatus === 1) {
      frm.add_custom_button(
        __("Purchase Invoice"),
        function () {
          frm.events.make_purchase_invoice(frm);
        },
        __("Create"),
      );
    }
  },
  make_purchase_invoice: function (frm) {
    let method = "sth.overrides.training_event.get_purchase_invoice_for_training_event";
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
  make_payment_entry: function (frm) {
    let method = "sth.overrides.training_event.get_payment_entry_for_training_event";
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
  }
});

frappe.ui.form.on("Training Event Costing", {
  total_amount(frm, cdt, cdn) {
    calculate_total_costing(frm);
  },
  custom_costing_remove(frm, cdt, cdn) {
    calculate_total_costing(frm);
  }
});

function calculate_total_costing(frm) {
  let total = 0;
  (frm.doc.custom_costing || []).forEach(row => {
    total += flt(row.total_amount);
  });
  frm.set_value("custom_grand_total_costing", total);
  frm.refresh_field("custom_grand_total_costing");
}