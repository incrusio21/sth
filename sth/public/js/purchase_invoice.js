frappe.ui.form.on("Purchase Invoice", {
  refresh(frm) {
    console.log(frm.doc.custom_reference_doctype);
    frm.fields_dict.items.grid.update_docfield_property(
      "custom_receipt_attachment",
      "hidden",
      frm.doc.custom_reference_doctype !== "Training Event"
    );

    frm.add_custom_button(
      __("Training Event"),
      function () {
        showTrainingEventSelector(frm);
      },
      __("Get Items From")
    );
  }
});

async function showTrainingEventSelector(frm) {
  if (!(frm.doc.supplier)) {
    frappe.msgprint(__("Lengkapi Supplier terlebih dahulu."));
    return;
  }

  const fields = [
    {
      fieldtype: 'Link',
      fieldname: 'name',
      label: 'Training Event',
      in_list_view: true
    },
    {
      fieldtype: 'Link',
      fieldname: 'supplier',
      label: 'Supplier',
      in_list_view: true
    },
    {
      fieldtype: 'Date',
      fieldname: 'custom_posting_date',
      label: 'Posting Date',
      in_list_view: true
    },
  ];

  let d = new frappe.ui.Dialog({
    title: 'Select Training Event',
    size: 'large',
    fields: [
      {
        label: 'Training Event',
        fieldname: 'table_training_event',
        fieldtype: 'Table',
        cannot_add_rows: true,
        in_place_edit: false,
        fields: fields
      }
    ],
    primary_action_label: 'Submit',
    async primary_action() {
      const selected_items = d.fields_dict.table_training_event.grid.get_selected_children();

      if (selected_items.length < 1) {
        frappe.throw("Please Select at least One Training Event")
      }

      const training_events = selected_items.map(r => r.name);
      const consting_items = await frappe.call({
        method: "sth.overrides.purchase_invoice.get_item_costing_in_training_events",
        args: {
          training_events: training_events
        },
        freeze: true,
        freeze_message: "Mengambil costing training event...",
      });

      for (const costing of consting_items.message) {
        frm.add_child("items", {
          item_code: costing.item,
          item_name: costing.item_code,
          qty: 1,
          uom: costing.stock_uom,
          rate: costing.total_amount,
          base_rate: costing.total_amount,
          amount: costing.total_amount,
          base_amount: costing.total_amount,
        })
      }

      frm.fields_dict.items.grid.update_docfield_property(
        "custom_receipt_attachment",
        "hidden",
        false
      );
      frm.refresh_field("items");
      frm.trigger("calculate_taxes_and_totals");
      d.hide();
    }
  });

  const training_events = await frappe.call({
    method: "sth.overrides.purchase_invoice.get_all_training_event_by_supplier",
    args: {
      supplier: frm.doc.supplier
    },
  });

  if (training_events.message) {
    d.fields_dict.table_training_event.df.data = training_events.message;
    d.fields_dict.table_training_event.refresh();
  }
  frm.clear_table("items");
  d.show();
}