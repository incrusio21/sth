// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.off("Payment Entry", "validate_reference_document");
frappe.ui.form.on("Payment Entry", {
    refresh(frm) {
        frm.set_query("reference_doctype", "references", function () {
            return {
                query: "sth.hr_customize.custom.payment_entry.get_payment_reference",
                filters: { 
                    party_type: frm.doc.party_type 
                },
            };
        });
        
        frm.set_query('custom_cheque_number', () => {
            return {
                filters: {
                    reference_doc: ["=", null], 
                    reference_name: ["=", null], 
                    bank_account: ["=", frm.doc.bank_account] 
                }
            }
        })
        
        frm.set_query('unit', (doc) => {
            return {
                filters: {
                    company: ["=", doc.company],
                }
            }
        })

        frm.set_query('reference_name', "references", (doc) => {
            return {
                filters: {
                    docstatus: 1,
                    company: ["=", doc.company],
                    unit: doc.unit   
                }
            }
        })

        frm.set_query('bank_account', (doc) => {
            return {
                filters: {
                    unit: ["=", doc.unit],
                    company: ["=", doc.company],
                }
            }
        })
        frm.ignore_doctypes_on_cancel_all = ["Deposito Interest"];
    },
    party_type(frm){
        frm.set_value("internal_employee", 0)
    },
    unit(frm){
        if(!frm.doc.unit) return
        
        frm.clear_table("references")
        frm.refresh_field("references")
    },
    internal_employee(frm){
        if(!frm.doc.internal_employee) return

        frappe.call({
            method: "sth.hr_customize.custom.payment_entry.get_internal_employee",
            callback(data){
                frm.set_value("party", data.message)
            }
        })
    },

    validate_reference_document: function (frm, row) {
		var _validate = function (i, row) {
			if (!row.reference_doctype) {
				return;
			}

			if (
				frm.doc.party_type == "Customer" &&
				!["Sales Order", "Sales Invoice", "Journal Entry", "Dunning", "Deposito Interest"].includes(row.reference_doctype)
			) {
				frappe.model.set_value(row.doctype, row.name, "reference_doctype", null);
				frappe.msgprint(
					__(
						"Row #{0}: Reference Document Type must be one of Sales Order, Sales Invoice, Journal Entry or Dunning, Deposito Interest",
						[row.idx]
					)
				);
				return false;
			}

			if (
				frm.doc.party_type == "Supplier" &&
				!["Purchase Order", "Purchase Invoice", "Journal Entry"].includes(row.reference_doctype)
			) {
				frappe.model.set_value(row.doctype, row.name, "against_voucher_type", null);
				frappe.msgprint(
					__(
						"Row #{0}: Reference Document Type must be one of Purchase Order, Purchase Invoice or Journal Entry",
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
	},

});
