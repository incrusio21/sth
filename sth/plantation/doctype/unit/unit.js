// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Unit", {
    refresh(frm) {
        frm.set_query("default_bank_account", () => {
            return {
                filters: {
                    "unit": frm.doc.name,
                    "company": frm.doc.company
                }
            }
        });

        frm.set_query("bank_account", () => {
            return {
                filters: {
                    "account_type": "Bank",
                    "company": frm.doc.company
                }
            }
        });

        frm.set_query("account_for_cash", () => {
            return {
                filters: {
                    "account_type": "Cash",
                    "company": frm.doc.company
                }
            }
        });

        const default_account_fields = [
            "default_bonus_account",
            "default_bonus_salary_account",
            "default_thr_account",
            "default_thr_salary_account",
            "default_phk_account",
            "default_phk_salary_account",
        ];

        default_account_fields.forEach(function (default_account) {
            frm.set_query(default_account, () => {
                return {
                    filters: {
                        "company": frm.doc.company
                    }
                }
            });
        });
    },
});
