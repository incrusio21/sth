// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Invoice", {
    refresh(frm) {
        if(frm.doc.docstatus == 0){
            frm.add_custom_button(
                __("BAPP"),
                function () {
                    erpnext.utils.map_current_doc({
                        method: "sth.legal.doctype.bapp.bapp.make_purchase_invoice",
                        source_doctype: "BAPP",
                        target: frm,
                        setters: {
                            supplier: frm.doc.supplier || undefined,
                            posting_date: undefined,
                        },
                        get_query_filters: {
                            docstatus: 1,
                            status: ["not in", ["Closed", "Completed", "Return Issued"]],
                            company: frm.doc.company,
                        },
                    });
                },
                __("Get Items From")
            );

            frm.add_custom_button(
                __("Proposal"),
                function () {
                    let d = new frappe.ui.Dialog({
                        title: 'Get Proposal',
                        fields: [
                            {
                                label: 'Supplier',
                                fieldname: 'supplier',
                                fieldtype: 'Link',
                                options: 'Supplier',
                                default: frm.doc.supplier,
                                onchange: function () {
                                    d.set_value("proposal", "")
                                }
                            },
                            {
                                label: 'Proposal',
                                fieldname: 'proposal',
                                fieldtype: 'Link',
                                options: 'Proposal',
                                reqd: 1,
                                get_query: () => {
                                    let filters = {                                        
                                        docstatus: 1,
                                        status: ["not in", ["Closed", "Completed", "Return Issued"]],
                                        company: frm.doc.company,
                                        is_bapp_retensi: 0
                                    }
                                    if (d.get_value("supplier")){
                                        filters["supplier"] = d.get_value("supplier")
                                    }
                                    return {
                                        filters: filters
                                    };
                                },
                                onchange: function () {
                                    frappe.call({
                                        method: "sth.legal.custom.purchase_invoice.get_proposal_termin",
                                        args: { proposal: this.value },
                                        callback: (r) => {
                                            if (!r.exc) {
                                                d.set_value("termin", "")
                                                d.fields_dict.termin.df.options = r.message
                                                d.fields_dict.termin.set_options()
                                            }
                                        },
                                    });
                                }
                            },
                            {
                                label: 'Termin',
                                fieldname: 'termin',
                                fieldtype: 'Select',
                                reqd: 1,
                            }
                        ],
                        primary_action_label: 'Get Items',
                        primary_action(values) {
                            cur_frm.doc.items = []
                            
                            frappe.call({
                                // Sometimes we hit the limit for URL length of a GET request
                                // as we send the full target_doc. Hence this is a POST request.
                                type: "POST",
                                method: "frappe.model.mapper.map_docs",
                                args: {
                                    method: "sth.legal.doctype.proposal.proposal.make_purchase_invoice",
                                    source_names: [values.proposal],
                                    target_doc: cur_frm.doc,
                                    args: {
                                        term: values.termin
                                    },
                                },
                                freeze: true,
                                freeze_message: __("Mapping {0} ...", ["Proposal"]),
                                callback: function (r) {
                                    if (!r.exc) {
                                        frappe.model.sync(r.message);
                                        cur_frm.dirty();
                                        cur_frm.refresh();
                                    }
                                },
                            });
                            d.hide();
                        }
                    });

                    d.show()
                    // erpnext.utils.map_current_doc({
                    //     method: "sth.legal.doctype.bapp.bapp.make_purchase_invoice",
                    //     source_doctype: "BAPP",
                    //     target: frm,
                    //     setters: {
                    //         supplier: frm.doc.supplier || undefined,
                    //         posting_date: undefined,
                    //     },
                    //     get_query_filters: {
                    //         docstatus: 1,
                    //         status: ["not in", ["Closed", "Completed", "Return Issued"]],
                    //         company: frm.doc.company,
                    //     },
                    // });
                },
                __("Get Items From")
            );
        }
    },
})