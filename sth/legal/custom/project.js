// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Project", {
    setup(frm){
        frm.add_fetch("project_type", "default_department", "department");
        // frm.add_fetch("proposal", "company", "company");
        // frm.add_fetch("proposal", "supplier", "supplier");
        // frm.add_fetch("proposal", "supplier_address_active", "supplier_address");
    },
    refresh(frm) {
        frm.set_query("project", () =>{
            return {
                filters:{
                    docstatus: 1,
                }
            }
        })
        
        frm.set_query("proposal", (doc) =>{
            return {
                filters:{
                    proposal_type: ["=", doc.proposal_type],
                    // docstatus: 1,
                }
            }
        })

        frm.set_query("purchase_order", (doc) =>{
            return {
                filters:{
                    need_project: ["=", 1],
                    // docstatus: 1,
                }
            }
        })

        if (frm.doc.status !== "Cancelled" && frm.doc.for_proposal) {
            frm.add_custom_button(
                __("Adendum"), () => {
                    frappe.model.open_mapped_doc({
                        method: "sth.legal.custom.project.make_project_adendum",
                        frm: cur_frm,
                        freeze_message: __("Adendum Revision ..."),
                    });
                },
                __("Create")
            );
        }

        if (!frm.is_new()) {
            frm.add_custom_button(__('Download PDF'), function() {
                frm.trigger("download_pdf")
            })
        }
	},
    proposal(frm){
        frm.events.get_details_data(frm, "Proposal", frm.doc.proposal)
    },
    purchase_order(frm){
        frm.events.get_details_data(frm, "Purchase Order", frm.doc.purchase_order)
    },
    get_details_data(frm, doctype, docname){
        frappe.call({
            method: "sth.legal.custom.project.get_proposal_data",
            args: {
                doctype: doctype,
                docname: docname
            },
            callback: (r) => {
                if(r.message){
                    $.each(r.message, function(k, v) {
                        frm.doc[k] = v;
                    });

                    frm.refresh_fields()
                }
            }
        })
    },

    contract_template: function (frm) {
		if (frm.doc.contract_template) {
			frappe.call({
				method: "sth.legal.custom.project.get_contract_template",
				args: {
					template_name: frm.doc.contract_template,
					doc: frm.doc,
				},
				callback: function (r) {
					if (r && r.message) {
						let contract_template = r.message.contract_template;
						frm.set_value("contract_term", r.message.contract_terms);
						frm.set_value("contract_cover", r.message.contract_cover);
						frm.set_value("contract_footer", r.message.contract_footer);
						// frm.set_value("requires_fulfilment", contract_template.requires_fulfilment);

						// if (frm.doc.requires_fulfilment) {
						// 	// Populate the fulfilment terms table from a contract template, if any
						// 	r.message.contract_template.fulfilment_terms.forEach((element) => {
						// 		let d = frm.add_child("fulfilment_terms");
						// 		d.requirement = element.requirement;
						// 	});
						// 	frm.refresh_field("fulfilment_terms");
						// }
					}
				},
			});
		}
	},

    download_pdf(frm){
        // Use window.open to download PDF
        var url = `/api/method/sth.overrides.contract_template.download_contract_pdf`;
        url += `?doctype=${encodeURIComponent(frm.doc.doctype)}&docname=${encodeURIComponent(frm.doc.name)}&print_format=${encodeURIComponent("Project Contract Term")}`

        window.open(url, '_blank');
        
        frappe.show_alert({
            message: __('Downloading PDF...'),
            indicator: 'green'
        });
    }
});