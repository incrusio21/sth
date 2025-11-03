// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.off('Loan', "onload")
frappe.ui.form.off('Loan', "loan_application")

frappe.ui.form.on('Loan', {
    onload: function (frm) {
        if(frm.doc.loan_application){
            loan_application_fields.forEach(field => { frm.set_df_property(field, 'read_only', 1); });
        }

		// Ignore Loan Security Assignment on cancel of loan
		frm.ignore_doctypes_on_cancel_all = ["Loan Security Assignment", "Loan Repayment Schedule", "Sales Invoice",
			"Loan Transfer", "Journal Entry"];

		frm.set_query("loan_application", function () {
			return {
				"filters": {
					"applicant": frm.doc.applicant,
					"docstatus": 1,
					"status": "Approved"
				}
			};
		});

		frm.set_query("loan_product", function () {
			return {
				"filters": {
					"company": frm.doc.company
				}
			};
		});

		$.each(["penalty_income_account", "interest_income_account"], function(i, field) {
			frm.set_query(field, function () {
				return {
					"filters": {
						"company": frm.doc.company,
						"root_type": "Income",
						"is_group": 0
					}
				};
			});
		});

		$.each(["payment_account", "loan_account", "disbursement_account"], function (i, field) {
			frm.set_query(field, function () {
				return {
					"filters": {
						"company": frm.doc.company,
						"root_type": "Asset",
						"is_group": 0
					}
				};
			});
		})

	},
	loan_application: function (frm) {
		if(frm.doc.loan_application){
			return frappe.call({
				method: "lending.loan_management.doctype.loan.loan.get_loan_application",
				args: {
					"loan_application": frm.doc.loan_application
				},
				callback: function (r) {
					if (!r.exc && r.message) {
						loan_application_fields.forEach(field => {
							frm.set_df_property(field, 'read_only', 1);
							frm.set_value(field, field == "monthly_repayment_amount" ? r.message["repayment_amount"]  : r.message[field]);
						});
						if (frm.doc.is_secured_loan) {
							$.each(r.message.proposed_pledges, function(i, d) {
								let row = frm.add_child("securities");
								row.loan_security = d.loan_security;
								row.qty = d.qty;
								row.loan_security_price = d.loan_security_price;
								row.amount = d.amount;
								row.haircut = d.haircut;
							});

							frm.refresh_fields("securities");
						}
					}
				}
			});
		}
		else {
			loan_application_fields.forEach(field => {
				frm.set_df_property(field, 'read_only', 0);
			});
		}
	}
})