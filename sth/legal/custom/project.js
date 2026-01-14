// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Project", {
    setup(frm){
        frm.add_fetch("project_type", "default_department", "department");
        frm.add_fetch("contract_template", "contract_terms", "contract_term");
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
    }
});