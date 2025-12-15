frappe.ui.form.on("Purchase Invoice", {
  setup(frm) {
    frm.set_query("nomor_pembelian", function (doc) {
      return {
        filters: {
          docstatus: 1
        }
      }
    })
  },

  refresh(frm) {
    frm.set_query("purchase_type", () => {
      return {
        filters: {
          document_type: frm.doctype
        }
      }
    })

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
  },

  nomor_pembelian(frm) {
    function _map(data) {
      frm.set_value({
        supplier: data.nama_supplier,
        unit: data.unit,
        buying_price_list: data.jarak
      })

      frm.clear_table("items")

      for (const row of data.items) {
        let item = frm.add_child("items")
        item.item_code = row.item_code
        item.qty = row.qty
        item.rate = row.rate
        item.amount = row.total
        frm.script_manager.trigger("item_code", item.doctype, item.name)
      }

      if (data.beban_pph_22) {
        frappe.xcall("sth.custom.purchase_invoice.get_default_coa", { company: frm.doc.company, type: "PPH 22" }).then((res) => {
          if (!res) {
            return
          }
          frm.clear_table("taxes")
          let item = frm.add_child("taxes")
          item.charge_type = "On Net Total"
          item.account_head = res
          item.rate = data.percent
          // frm.script_manager.trigger("rate", item.doctype, item.name)

        })
      }

      refresh_field("items")
      refresh_field("taxes")
    }

    if (frm.doc.nomor_pembelian) {
      frappe.dom.freeze("Mapping Data...")
      frappe.xcall("frappe.client.get", { doctype: "Pengakuan Pembelian TBS", name: frm.doc.nomor_pembelian })
        .then((res) => {
          frappe.run_serially([
            () => _map(res),
            () => frappe.dom.unfreeze()
          ])
        })
    }

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

      if (selected_items.length != 1) {
        frappe.throw("Select Only One Training Event")
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

      frm.set_value("custom_reference_doctype", "Training Event");
      frm.set_value("custom_reference_name", selected_items[0].name);
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