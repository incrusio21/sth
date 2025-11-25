frappe.ui.form.on("Purchase Invoice", {
  refresh(frm) {
    frm.fields_dict.items.grid.update_docfield_property(
      "custom_receipt_attachment",
      "hidden",
      frm.doc.custom_reference_doctype !== "Training Event"
    );
  }
});