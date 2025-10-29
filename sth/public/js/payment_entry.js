frappe.ui.form.on("Payment Entry", {
  refresh(frm) {
    frm.set_query("reference_doctype", "references", function () {
      let doctypes = ["Journal Entry"];
      if (frm.doc.party_type == "Customer") {
        doctypes = ["Sales Order", "Sales Invoice", "Journal Entry", "Dunning"];
      } else if (frm.doc.party_type == "Supplier") {
        doctypes = ["Purchase Order", "Purchase Invoice", "Journal Entry", "Training Event", "Travel Request"];
      }

      return {
        filters: { name: ["in", doctypes] },
      };
    });
  },
  validate_reference_document: function (frm, row) {
    var _validate = function (i, row) {
      if (!row.reference_doctype) {
        return;
      }

      if (
        frm.doc.party_type == "Customer" &&
        !["Sales Order", "Sales Invoice", "Journal Entry", "Dunning", "Training Event", "Travel Request"].includes(row.reference_doctype)
      ) {
        frappe.model.set_value(row.doctype, row.name, "reference_doctype", null);
        frappe.msgprint(
          __(
            "Row #{0}: Reference Document Type must be one of Sales Order, Sales Invoice, Journal Entry or Dunning",
            [row.idx]
          )
        );
        return false;
      }

      if (
        frm.doc.party_type == "Supplier" &&
        !["Purchase Order", "Purchase Invoice", "Journal Entry", "Training Event", "Travel Request"].includes(row.reference_doctype)
      ) {
        frappe.model.set_value(row.doctype, row.name, "against_voucher_type", null);
        frappe.msgprint(
          __(
            "Row #{0}: Reference Document Type must be one of Purchase Order, Training Event, Travel Request, Purchase Invoice or Journal Entry",
            [row.idx]
          )
        );
        return false;
      }
    };

    if (row) {
      _validate(0, row);
    } else {
      $.each(frm.doc.vouchers || [], _validate);
    }
  }
});

frappe.ui.form.on("Payment Entry Reference", {
  reference_doctype: function (frm, cdt, cdn) {
    var row = locals[cdt][cdn];
    frm.events.validate_reference_document(frm, row);
    console.log(row);
  },
});