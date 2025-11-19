erpnext.accounts.PurchaseInvoice = class PurchaseInvoice extends erpnext.buying.BuyingController {
  refresh(doc) {
    console.log("custom purchase invoice");
    const me = this;
    super.refresh();

    hide_fields(this.frm.doc);
    // Show / Hide button
    this.show_general_ledger();
    erpnext.accounts.ledger_preview.show_accounting_ledger_preview(this.frm);

    if (doc.update_stock == 1) {
      this.show_stock_ledger();
      erpnext.accounts.ledger_preview.show_stock_ledger_preview(this.frm);
    }

    if (!doc.is_return && doc.docstatus == 1 && doc.outstanding_amount != 0) {
      if (doc.on_hold) {
        this.frm.add_custom_button(
          __("Change Release Date"),
          function () {
            me.change_release_date();
          },
          __("Hold Invoice")
        );
        this.frm.add_custom_button(
          __("Unblock Invoice"),
          function () {
            me.unblock_invoice();
          },
          __("Create")
        );
      } else if (!doc.on_hold) {
        this.frm.add_custom_button(
          __("Block Invoice"),
          function () {
            me.block_invoice();
          },
          __("Create")
        );
      }
    }

    if (doc.docstatus == 1 && doc.outstanding_amount != 0 && !doc.on_hold) {
      this.frm.add_custom_button(__("Payment"), () => this.make_payment_entry(), __("Create"));
      cur_frm.page.set_inner_btn_group_as_primary(__("Create"));
    }

    if (!doc.is_return && doc.docstatus == 1) {
      if (doc.outstanding_amount >= 0 || Math.abs(flt(doc.outstanding_amount)) < flt(doc.grand_total)) {
        cur_frm.add_custom_button(__("Return / Debit Note"), this.make_debit_note, __("Create"));
      }
    }

    if (doc.outstanding_amount > 0 && !cint(doc.is_return) && !doc.on_hold) {
      cur_frm.add_custom_button(
        __("Payment Request"),
        function () {
          me.make_payment_request();
        },
        __("Create")
      );
    }

    if (doc.docstatus === 0) {
      this.frm.add_custom_button(
        __("Purchase Order"),
        function () {
          erpnext.utils.map_current_doc({
            method: "erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_invoice",
            source_doctype: "Purchase Order",
            target: me.frm,
            setters: {
              supplier: me.frm.doc.supplier || undefined,
              schedule_date: undefined,
            },
            get_query_filters: {
              docstatus: 1,
              status: ["not in", ["Closed", "On Hold"]],
              per_billed: ["<", 99.99],
              company: me.frm.doc.company,
            },
            allow_child_item_selection: true,
            child_fieldname: "items",
            child_columns: ["item_code", "item_name", "qty", "amount", "billed_amt"],
          });
        },
        __("Get Items From")
      );

      this.frm.add_custom_button(
        __("Purchase Receipt"),
        function () {
          erpnext.utils.map_current_doc({
            method: "erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_purchase_invoice",
            source_doctype: "Purchase Receipt",
            target: me.frm,
            setters: {
              supplier: me.frm.doc.supplier || undefined,
              posting_date: undefined,
            },
            get_query_filters: {
              docstatus: 1,
              status: ["not in", ["Closed", "Completed", "Return Issued"]],
              company: me.frm.doc.company,
              is_return: 0,
            },
            allow_child_item_selection: true,
            child_fieldname: "items",
            child_columns: ["item_code", "item_name", "qty", "amount", "billed_amt"],
          });
        },
        __("Get Items From")
      );

      // this.frm.add_custom_button(
      //   __("Expense Claim"),
      //   function () {
      //     const fields = [
      //       {
      //         fieldtype: 'Link',
      //         fieldname: 'custom_travel_request',
      //         label: 'Travel Request',
      //         in_list_view: true
      //       },
      //       {
      //         fieldtype: 'Link',
      //         fieldname: 'costing_expense',
      //         label: 'Costing Expense',
      //         hidden: true
      //       },
      //       {
      //         fieldtype: 'Date',
      //         fieldname: 'expense_date',
      //         label: 'Expense Date',
      //         in_list_view: true
      //       },
      //       {
      //         fieldtype: 'Date',
      //         fieldname: 'custom_estimate_depart_date',
      //         label: 'Estimate Depart Date',
      //         in_list_view: true
      //       },
      //       {
      //         fieldtype: 'Date',
      //         fieldname: 'custom_estimate_arrival_date',
      //         label: 'Estimate Arrival Date',
      //         in_list_view: true
      //       },
      //       {
      //         fieldtype: 'Link',
      //         fieldname: 'expense_type',
      //         label: 'Expense Type',
      //         in_list_view: true
      //       },
      //       {
      //         fieldtype: 'Link',
      //         fieldname: 'default_account',
      //         label: 'Default Account',
      //         in_list_view: true
      //       },
      //       {
      //         fieldtype: 'Currency',
      //         fieldname: 'amount',
      //         label: 'Amount',
      //         in_list_view: true
      //       },
      //       {
      //         fieldtype: 'Currency',
      //         fieldname: 'sanctioned_amount',
      //         label: 'Sanctioned_amount',
      //         in_list_view: true
      //       },
      //     ];

      //     let d = new frappe.ui.Dialog({
      //       title: 'Select Expense',
      //       size: 'large',
      //       fields: [
      //         {
      //           label: 'Expenses',
      //           fieldname: 'expenses',
      //           fieldtype: 'Table',
      //           cannot_add_rows: true,
      //           in_place_edit: false,
      //           fields: fields
      //         }
      //       ],
      //       primary_action_label: 'Submit',
      //       primary_action() {
      //         const selected_items = d.fields_dict.expenses.grid.get_selected_children();

      //         if (selected_items.length < 1) {
      //           frappe.throw("Please Select at least One Expense")
      //         }

      //         frm.refresh_field("expenses");
      //         d.hide();
      //       }
      //     });
      //     d.show();
      //   },
      //   __("Get Items From")
      // );

      if (!this.frm.doc.is_return) {
        frappe.db.get_single_value("Buying Settings", "maintain_same_rate").then((value) => {
          if (value) {
            this.frm.doc.items.forEach((item) => {
              this.frm.fields_dict.items.grid.update_docfield_property(
                "rate",
                "read_only",
                item.purchase_receipt && item.pr_detail
              );
            });
          }
        });
      }
    }
    this.frm.toggle_reqd("supplier_warehouse", this.frm.doc.is_subcontracted);

    if (doc.docstatus == 1 && !doc.inter_company_invoice_reference) {
      frappe.model.with_doc("Supplier", me.frm.doc.supplier, function () {
        var supplier = frappe.model.get_doc("Supplier", me.frm.doc.supplier);
        var internal = supplier.is_internal_supplier;
        var disabled = supplier.disabled;
        if (internal == 1 && disabled == 0) {
          me.frm.add_custom_button(
            "Inter Company Invoice",
            function () {
              me.make_inter_company_invoice(me.frm);
            },
            __("Create")
          );
        }
      });
    }

    this.frm.set_df_property("tax_withholding_category", "hidden", doc.apply_tds ? 0 : 1);
    erpnext.accounts.unreconcile_payment.add_unreconcile_btn(me.frm);
  }
};
cur_frm.script_manager.make(erpnext.accounts.PurchaseInvoice);
