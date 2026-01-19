frappe.provide("erpnext.utils");

erpnext.utils.map_current_doc_original = erpnext.utils.map_current_doc;

erpnext.utils.map_current_doc = function (opts) {
    function _map() {
        if ($.isArray(cur_frm.doc.items) && cur_frm.doc.items.length > 0) {
            // remove first item row if empty
            if (!cur_frm.doc.items[0].item_code) {
                cur_frm.doc.items = cur_frm.doc.items.splice(1);
            }

            // find the doctype of the items table
            var items_doctype = frappe.meta.get_docfield(cur_frm.doctype, "items").options;

            // find the link fieldname from items table for the given
            // source_doctype
            var link_fieldname = null;
            frappe.get_meta(items_doctype).fields.forEach(function (d) {
                if (d.options === opts.source_doctype) link_fieldname = d.fieldname;
            });

            // search in existing items if the source_name is already set and full qty fetched
            var already_set = false;
            var item_qty_map = {};

            $.each(cur_frm.doc.items, function (i, d) {
                opts.source_name.forEach(function (src) {
                    if (d[link_fieldname] == src) {
                        already_set = true;
                        if (item_qty_map[d.item_code]) item_qty_map[d.item_code] += flt(d.qty);
                        else item_qty_map[d.item_code] = flt(d.qty);
                    }
                });
            });

            if (already_set) {
                opts.source_name.forEach(function (src) {
                    frappe.model.with_doc(opts.source_doctype, src, function (r) {
                        var source_doc = frappe.model.get_doc(opts.source_doctype, src);
                        $.each(source_doc.items || [], function (i, row) {
                            if (row.qty > flt(item_qty_map[row.item_code])) {
                                already_set = false;
                                return false;
                            }
                        });
                    });

                    if (already_set) {
                        frappe.msgprint(
                            __("You have already selected items from {0} {1}", [opts.source_doctype, src])
                        );
                        return;
                    }
                });
            }
        }

        return frappe.call({
            // Sometimes we hit the limit for URL length of a GET request
            // as we send the full target_doc. Hence this is a POST request.
            type: "POST",
            method: "frappe.model.mapper.map_docs",
            args: {
                method: opts.method,
                source_names: opts.source_name,
                target_doc: cur_frm.doc,
                args: opts.args,
            },
            freeze: true,
            freeze_message: __("Mapping {0} ...", [opts.source_doctype]),
            callback: function (r) {
                if (!r.exc) {
                    frappe.model.sync(r.message);
                    cur_frm.dirty();
                    cur_frm.refresh();
                }
            },
        });
    }

    let query_args = {};
    if (opts.get_query_filters) {
        query_args.filters = opts.get_query_filters;
    }

    if (opts.get_query_method) {
        query_args.query = opts.get_query_method;
    }

    if (query_args.filters || query_args.query) {
        opts.get_query = () => query_args;
    }

    if (opts.source_doctype) {
        let data_fields = [];
        if (["Purchase Receipt", "Delivery Note"].includes(opts.source_doctype)) {
            let target_meta = frappe.get_meta(cur_frm.doc.doctype);
            if (target_meta.fields.find((f) => f.fieldname === "taxes")) {
                data_fields.push({
                    fieldname: "merge_taxes",
                    fieldtype: "Check",
                    label: __("Merge taxes from multiple documents"),
                });
            }
        }
        const d = new frappe.ui.form.MultiSelectDialog({
            doctype: opts.source_doctype,
            target: opts.target,
            date_field: opts.date_field || undefined,
            setters: opts.setters,
            read_only_setters: opts.read_only_setters,
            data_fields: data_fields,
            get_query: opts.get_query,
            add_filters_group: 1,
            allow_child_item_selection: opts.allow_child_item_selection,
            child_fieldname: opts.child_fieldname,
            child_columns: opts.child_columns,
            size: opts.size,
            action: function (selections, args) {
                let values = selections;
                if (values.length === 0) {
                    frappe.msgprint(__("Please select {0}", [opts.source_doctype]));
                    return;
                }

                if (values.constructor === Array) {
                    opts.source_name = [...new Set(values)];
                } else {
                    opts.source_name = values;
                }

                if (
                    opts.allow_child_item_selection ||
                    ["Purchase Receipt", "Delivery Note", "Pick List"].includes(opts.source_doctype)
                ) {
                    // args contains filtered child docnames
                    opts.args = args;
                }
                d.dialog.hide();
                _map();
            },
        });

        return d;
    }

    if (opts.source_name) {
        opts.source_name = [opts.source_name];
        _map();
    }
};


erpnext.accounts.PurchaseInvoice = class PurchaseInvoice extends erpnext.buying.BuyingController {
    setup(doc) {
        this.setup_posting_date_time_check();
        super.setup(doc);

        // formatter for purchase invoice item
        if (this.frm.doc.update_stock) {
            this.frm.set_indicator_formatter("item_code", function (doc) {
                return doc.qty <= doc.received_qty ? "green" : "orange";
            });
        }

        this.frm.set_query("unrealized_profit_loss_account", function () {
            return {
                filters: {
                    company: doc.company,
                    is_group: 0,
                    root_type: "Liability",
                },
            };
        });

        this.frm.set_query("expense_account", "items", function () {
            return {
                query: "erpnext.controllers.queries.get_expense_account",
                filters: { company: doc.company },
            };
        });
    }

    onload() {
        super.onload();

        // Ignore linked advances
        this.frm.ignore_doctypes_on_cancel_all = [
            "Journal Entry",
            "Payment Entry",
            "Purchase Invoice",
            "Repost Payment Ledger",
            "Repost Accounting Ledger",
            "Unreconcile Payment",
            "Unreconcile Payment Entries",
            "Serial and Batch Bundle",
            "Bank Transaction",
        ];

        if (!this.frm.doc.__islocal) {
            // show credit_to in print format
            if (!this.frm.doc.supplier && this.frm.doc.credit_to) {
                this.frm.set_df_property("credit_to", "print_hide", 0);
            }
        }

        // Trigger supplier event on load if supplier is available
        // The reason for this is PI can be created from PR or PO and supplier is pre populated
        if (this.frm.doc.supplier && this.frm.doc.__islocal) {
            this.frm.trigger("supplier");
        }
    }

    refresh(doc) {
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
                    });
                },
                __("Get Items From")
            );

            this.frm.add_custom_button(
                __("Purchase Receipts"),
                function () {
                    erpnext.utils.map_current_doc({
                        method: "erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_purchase_invoice",
                        source_doctype: "Purchase Receipt",
                        target: me.frm,
                        setters: {
                            supplier: me.frm.doc.supplier || undefined,
                            posting_date: undefined,
                            purchase_order: undefined
                        },
                        get_query_filters: {
                            docstatus: 1,
                            status: ["not in", ["Closed", "Completed", "Return Issued"]],
                            company: me.frm.doc.company,
                            is_return: 0,
                        },
                    });
                },
                __("Get Items From")
            );

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

    unblock_invoice() {
        const me = this;
        frappe.call({
            method: "erpnext.accounts.doctype.purchase_invoice.purchase_invoice.unblock_invoice",
            args: { name: me.frm.doc.name },
            callback: (r) => me.frm.reload_doc(),
        });
    }

    block_invoice() {
        this.make_comment_dialog_and_block_invoice();
    }

    change_release_date() {
        this.make_dialog_and_set_release_date();
    }

    can_change_release_date(date) {
        const diff = frappe.datetime.get_diff(date, frappe.datetime.nowdate());
        if (diff < 0) {
            frappe.throw(__("New release date should be in the future"));
            return false;
        } else {
            return true;
        }
    }

    make_comment_dialog_and_block_invoice() {
        const me = this;

        const title = __("Block Invoice");
        const fields = [
            {
                fieldname: "release_date",
                read_only: 0,
                fieldtype: "Date",
                label: __("Release Date"),
                default: me.frm.doc.release_date,
                reqd: 1,
            },
            {
                fieldname: "hold_comment",
                read_only: 0,
                fieldtype: "Small Text",
                label: __("Reason For Putting On Hold"),
                default: "",
            },
        ];

        this.dialog = new frappe.ui.Dialog({
            title: title,
            fields: fields,
        });

        this.dialog.set_primary_action(__("Save"), function () {
            const dialog_data = me.dialog.get_values();
            frappe.call({
                method: "erpnext.accounts.doctype.purchase_invoice.purchase_invoice.block_invoice",
                args: {
                    name: me.frm.doc.name,
                    hold_comment: dialog_data.hold_comment,
                    release_date: dialog_data.release_date,
                },
                callback: (r) => me.frm.reload_doc(),
            });
            me.dialog.hide();
        });

        this.dialog.show();
    }

    make_dialog_and_set_release_date() {
        const me = this;

        const title = __("Set New Release Date");
        const fields = [
            {
                fieldname: "release_date",
                read_only: 0,
                fieldtype: "Date",
                label: __("Release Date"),
                default: me.frm.doc.release_date,
            },
        ];

        this.dialog = new frappe.ui.Dialog({
            title: title,
            fields: fields,
        });

        this.dialog.set_primary_action(__("Save"), function () {
            me.dialog_data = me.dialog.get_values();
            if (me.can_change_release_date(me.dialog_data.release_date)) {
                me.dialog_data.name = me.frm.doc.name;
                me.set_release_date(me.dialog_data);
                me.dialog.hide();
            }
        });

        this.dialog.show();
    }

    set_release_date(data) {
        return frappe.call({
            method: "erpnext.accounts.doctype.purchase_invoice.purchase_invoice.change_release_date",
            args: data,
            callback: (r) => this.frm.reload_doc(),
        });
    }

    supplier() {
        var me = this;

        // Do not update if inter company reference is there as the details will already be updated
        if (this.frm.updating_party_details || this.frm.doc.inter_company_invoice_reference) return;

        if (this.frm.doc.__onload && this.frm.doc.__onload.load_after_mapping) return;

        let payment_terms_template = this.frm.doc.payment_terms_template;

        erpnext.utils.get_party_details(
            this.frm,
            "erpnext.accounts.party.get_party_details",
            {
                posting_date: this.frm.doc.posting_date,
                bill_date: this.frm.doc.bill_date,
                party: this.frm.doc.supplier,
                party_type: "Supplier",
                account: this.frm.doc.credit_to,
                price_list: this.frm.doc.buying_price_list,
                fetch_payment_terms_template: cint(
                    (this.frm.doc.is_return == 0) & !this.frm.doc.ignore_default_payment_terms_template
                ),
            },
            function () {
                me.apply_pricing_rule();
                me.frm.doc.apply_tds = me.frm.supplier_tds ? 1 : 0;
                me.frm.doc.tax_withholding_category = me.frm.supplier_tds;
                me.frm.set_df_property("apply_tds", "read_only", me.frm.supplier_tds ? 0 : 1);
                me.frm.set_df_property("tax_withholding_category", "hidden", me.frm.supplier_tds ? 0 : 1);

                // while duplicating, don't change payment terms
                if (me.frm.doc.__run_link_triggers === false) {
                    me.frm.set_value("payment_terms_template", payment_terms_template);
                    me.frm.refresh_field("payment_terms_template");
                }
            }
        );
    }

    apply_tds(frm) {
        var me = this;
        me.frm.set_value("tax_withheld_vouchers", []);
        if (!me.frm.doc.apply_tds) {
            me.frm.set_value("tax_withholding_category", "");
            me.frm.set_df_property("tax_withholding_category", "hidden", 1);
        } else {
            me.frm.set_value("tax_withholding_category", me.frm.supplier_tds);
            me.frm.set_df_property("tax_withholding_category", "hidden", 0);
        }
    }

    tax_withholding_category(frm) {
        var me = this;
        let filtered_taxes = (me.frm.doc.taxes || []).filter((row) => !row.is_tax_withholding_account);
        me.frm.clear_table("taxes");

        filtered_taxes.forEach((row) => {
            me.frm.add_child("taxes", row);
        });

        me.frm.refresh_field("taxes");
    }

    credit_to() {
        var me = this;
        if (this.frm.doc.credit_to) {
            me.frm.call({
                method: "frappe.client.get_value",
                args: {
                    doctype: "Account",
                    fieldname: "account_currency",
                    filters: { name: me.frm.doc.credit_to },
                },
                callback: function (r, rt) {
                    if (r.message) {
                        me.frm.set_value("party_account_currency", r.message.account_currency);
                        me.set_dynamic_labels();
                    }
                },
            });
        }
    }

    make_inter_company_invoice(frm) {
        frappe.model.open_mapped_doc({
            method: "erpnext.accounts.doctype.purchase_invoice.purchase_invoice.make_inter_company_sales_invoice",
            frm: frm,
        });
    }

    is_paid() {
        hide_fields(this.frm.doc);
        if (cint(this.frm.doc.is_paid)) {
            this.frm.set_value("allocate_advances_automatically", 0);
            this.frm.set_value("payment_terms_template", "");
            this.frm.set_value("payment_schedule", []);
            if (!this.frm.doc.company) {
                this.frm.set_value("is_paid", 0);
                frappe.msgprint(__("Please specify Company to proceed"));
            }
        } else {
            this.frm.set_value("paid_amount", 0);
        }
        this.calculate_outstanding_amount();
        this.frm.refresh_fields();
    }

    write_off_amount() {
        this.set_in_company_currency(this.frm.doc, ["write_off_amount"]);
        this.calculate_outstanding_amount();
        this.frm.refresh_fields();
    }

    paid_amount() {
        this.set_in_company_currency(this.frm.doc, ["paid_amount"]);
        this.write_off_amount();
        this.frm.refresh_fields();
    }

    allocated_amount() {
        this.calculate_total_advance();
        this.frm.refresh_fields();
    }

    items_add(doc, cdt, cdn) {
        var row = frappe.get_doc(cdt, cdn);
        this.frm.script_manager.copy_from_first_row("items", row, [
            "expense_account",
            "discount_account",
            "cost_center",
            "project",
        ]);
    }

    on_submit() {
        super.on_submit();

        $.each(this.frm.doc["items"] || [], function (i, row) {
            if (row.purchase_receipt) frappe.model.clear_doc("Purchase Receipt", row.purchase_receipt);
        });
    }

    make_debit_note() {
        frappe.model.open_mapped_doc({
            method: "erpnext.accounts.doctype.purchase_invoice.purchase_invoice.make_debit_note",
            frm: cur_frm,
        });
    }
};

cur_frm.script_manager.make(erpnext.accounts.PurchaseInvoice);
