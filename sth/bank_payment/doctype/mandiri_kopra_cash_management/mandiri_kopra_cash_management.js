// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Mandiri Kopra Cash Management", {
// 	refresh(frm) {

// 	},
// });


const BANK_MAP = {
    "008": "Bank Mandiri",
    "009": "Bank BNI",
    "014": "Bank BCA",
    "002": "Bank BRI",
    "022": "CIMB Niaga",
    "011": "Bank Danamon",
    "013": "Bank Permata",
    "028": "Bank OCBC NISP",
    "016": "Maybank Indonesia",
    "019": "Bank Panin",
    "213": "Bank BTPN",
    "200": "Bank BTN",
    "451": "Bank Syariah Indonesia",
    "031": "Citibank",
    "087": "HSBC Indonesia",
    "426": "Bank Mega"
};

frappe.ui.form.on('Mandiri Kopra Cash Management', {
    refresh(frm) {

        if (frm.doc.docstatus === 1) {
            frm.add_custom_button('Check Payment Status', function () {

                frappe.call({
                    method: "sth.bank_payment.doctype.mandiri_kopra_cash_management.mandiri_kopra_cash_management.get_payment_status",
                    freeze: true,
                    freeze_message: "Checking payment status...",

                    callback: function (r) {
                        frappe.msgprint("Payment status updated");
                        frm.reload_doc();
                    }
                });

            });
        }

    }
});

frappe.ui.form.on('Mandiri Kopra Detail', {
    payment_entry: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (!row.payment_entry) return;

        frappe.call({
            method: "sth.bank_payment.doctype.mandiri_kopra_cash_management.mandiri_kopra_cash_management.get_payment_entry_details",
            args: {
                payment_entry: row.payment_entry
            },
            callback: function (r) {
                if (!r.message) return;

                let pe = r.message;

                frappe.model.set_value(cdt, cdn, "debit_account", pe.debit_account);
                frappe.model.set_value(cdt, cdn, "beneficiary_account", pe.beneficiary_account);
                
                frappe.model.set_value(cdt, cdn, "paid_from", pe.paid_from);
                frappe.model.set_value(cdt, cdn, "paid_to", pe.paid_to);

                frappe.model.set_value(cdt, cdn, "beneficiary_name", pe.beneficiary_name);
                frappe.model.set_value(cdt, cdn, "currency", pe.currency);
                frappe.model.set_value(cdt, cdn, "amount", pe.amount);
                frappe.model.set_value(cdt, cdn, "customer_reference", pe.customer_reference);

                frappe.model.set_value(cdt, cdn, "ft_service", "IBU");
                frappe.model.set_value(cdt, cdn, "bank_code", "");
                frappe.model.set_value(cdt, cdn, "remark", pe.remarks);
                frappe.model.set_value(cdt, cdn, "session", "1");

                frappe.model.set_value(cdt, cdn, "email_flag", "N");
                frappe.model.set_value(cdt, cdn, "email", "");
                frappe.model.set_value(cdt, cdn, "charge", "OUR");
                frappe.model.set_value(cdt, cdn, "beneficiary_type", 2);
            }
        });
    },
    bank_code: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (!row.bank_code) return;

        let bank_name = BANK_MAP[row.bank_code];

        if (bank_name) {
            frappe.model.set_value(cdt, cdn, "beneficiary_bank_name", bank_name);
        } else {
            frappe.model.set_value(cdt, cdn, "beneficiary_bank_name", "");
        }
    }
});

frappe.ui.form.on('Mandiri Kopra Cash Management', {
    setup(frm) {
        frm.set_query('payment_entry', 'detail', function () {
            return {
                filters: {
                    docstatus: 1
                }
            };
        });
    }
});


frappe.ui.form.on('Mandiri Kopra Cash Bill Detail', {
    payment_entry: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row.payment_entry) return;

        frappe.call({
            method: "sth.bank_payment.doctype.mandiri_kopra_cash_management.mandiri_kopra_cash_management.get_payment_entry_details",
            args: {
                payment_entry: row.payment_entry
            },
            callback: function (r) {
                if (!r.message) return;

                let pe = r.message;

                frappe.model.set_value(cdt, cdn, "paid_from", pe.paid_from);
                frappe.model.set_value(cdt, cdn, "debit_account", pe.debit_account);

                frappe.model.set_value(cdt, cdn, "currency", pe.currency);
                frappe.model.set_value(cdt, cdn, "amount", pe.amount);
                frappe.model.set_value(cdt, cdn, "bill_key_2", pe.amount);

                frappe.model.set_value(
                    cdt, cdn,
                    "transaction_reference",
                    pe.customer_reference || pe.remarks
                );

                frappe.model.set_value(cdt, cdn, "remark", pe.remarks);

                frappe.model.set_value(cdt, cdn, "ft_services", "UBP");

                frappe.model.set_value(cdt, cdn, "email", "");

                frappe.model.set_value(cdt, cdn, "extended_payment_detail", "");

            }
        });
    },
    amount: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (row.amount) {
            frappe.model.set_value(cdt, cdn, "bill_key_2", row.amount);
        }
    }
});


frappe.ui.form.on('Mandiri Kopra Cash Payroll Detail', {
    payment_entry: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row.payment_entry) return;

        frappe.call({
            method: "sth.bank_payment.doctype.mandiri_kopra_cash_management.mandiri_kopra_cash_management.get_payment_entry_details",
            args: {
                payment_entry: row.payment_entry
            },
            callback: function (r) {
                if (!r.message) return;

                let pe = r.message;

                frappe.model.set_value(cdt, cdn, "debit_account", pe.debit_account);
                frappe.model.set_value(cdt, cdn, "beneficiary_account", pe.beneficiary_account);
                frappe.model.set_value(cdt, cdn, "beneficiary_name", pe.beneficiary_name);
                frappe.model.set_value(cdt, cdn, "currency", pe.currency);
                frappe.model.set_value(cdt, cdn, "amount", pe.amount);

                frappe.model.set_value(cdt, cdn, "customer_reference", pe.customer_reference);
                frappe.model.set_value(cdt, cdn, "remark", pe.remarks);

                frappe.model.set_value(cdt, cdn, "ft_service", "IBU");   
                frappe.model.set_value(cdt, cdn, "bank_code", "");

                frappe.model.set_value(cdt, cdn, "email_flag", "N");
                frappe.model.set_value(cdt, cdn, "email", "");

                frappe.model.set_value(cdt, cdn, "charge", "OUR");
                frappe.model.set_value(cdt, cdn, "beneficiary_type", "2");

                frappe.model.set_value(
                    cdt,
                    cdn,
                    "extended_payment_detail",
                    `Payroll ${frappe.datetime.nowdate()} - ${pe.remarks || ""}`
                );
            }
        });
    }
});

