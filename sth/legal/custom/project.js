// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Project", {
    setup(frm){
        frm.add_fetch("project_type", "default_department", "department");
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
	},
    proposal(frm){
        if(!frm.doc.proposal) return

        frappe.call({
            method: "sth.legal.custom.project.get_proposal_data",
            args: {
                proposal: frm.doc.proposal
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
	}
});