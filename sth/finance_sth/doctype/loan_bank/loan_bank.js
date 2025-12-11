// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Loan Bank", {
	refresh(frm, cdt, cdn) {
        frappe.run_serially([            
            () => filterBankAccount(frm),
            () => filterUnit(frm),
            () => filterDisbursementNumber(frm, cdt, cdn),
            () => filterAccounting(frm),
            () => hideShowAngsuran(frm),
        ])
	},
    availability_period(frm){
        calculateScheduleLoan(frm);
    },
    grace_period(frm){
        calculateScheduleLoan(frm);
    },
    actual_number_of_payments(frm){
        calculateScheduleLoan(frm);
    },
    new_interest(frm){
        showInterestRateDialog(frm);
    }
});

frappe.ui.form.on("Disbursement Loan Bank", {
    disbursements_add(frm, cdt, cdn){
        getDisbursementNumber(frm, cdt, cdn)
    },
    disbursement_amount(frm, cdt, cdn){
        validateTotalAmountDisbursement(frm, cdt, cdn)
        totalAmountDisbursement(frm, cdt, cdn)
    },
    before_disbursements_remove(frm, cdt, cdn){
        validateDeleteDisbursement(frm, cdt, cdn)
    }
});

frappe.ui.form.on("Installment Loan Bank", {
    installments_add(frm, cdt, cdn){
        // getLastInterest(frm, cdt, cdn)
    },
    disbursement_number(frm, cdt, cdn){
        validateChangeInstallment(frm, cdt, cdn)
        checkGracePrincipal(frm, cdt, cdn)
        
    },
    payment_date(frm, cdt, cdn){
        getLastInterest(frm, cdt, cdn)
        getDaysInstallment(frm, cdt, cdn)
    },
    loan_interest(frm, cdt, cdn){
        calculateInterestAmount(frm, cdt, cdn)
    }
})

function filterBankAccount(frm) {
    frm.set_query('bank_account', () => {
        return{
            filters: {
                bank: frm.doc.bank,
                company: frm.doc.company
            }
        }
    })
}

function getDisbursementNumber(frm, cdt, cdn) {
    let length = frm.doc.disbursements.length.toString()
    let number = length.padStart(5, "0")
    const docname = frm.doc.name
    const disbursementNumber = `${docname}-${number}`
    frappe.model.set_value(cdt, cdn, "disbursement_number", disbursementNumber)
    frappe.model.set_value(cdt, cdn, "due_days", frm.doc.due_days)
    frm.refresh_field("disbursements")
}

function validateTotalAmountDisbursement(frm, cdt, cdn) {
    const curRow = locals[cdt][cdn];
    let totalDisbursement = getTotalDisbursement(frm);
    totalDisbursement += curRow.disbursement_amount;
    
    if (totalDisbursement > frm.doc.loan_amount) {
        frappe.throw(`<b>Total Pencairan</b> tidak boleh lebih besar dari <b>Jumlah Fasilitas</b>!!`)
    }
}

function getTotalDisbursement(frm) {
    let total = 0
    for (const row of frm.doc.disbursements) {
        total += row.disbursement_amount
    }

    return total
}

function validateDeleteDisbursement(frm, cdt, cdn) {
    const curRow = locals[cdt][cdn]

    for (const row of frm.doc.installments) {
        if (curRow.disbursement_number != row.disbursement_number) {
            continue
        }
        frappe.throw(`<b>No Pencairan: ${curRow.disbursement_number}</b> tidak bisa dihapus karena digunakan di <b>Angsuran Row ${curRow.idx}</b>, mohon hapus Angsuran terlebih dahulu`)
    }
}

function validateChangeInstallment(frm, cdt, cdn) {
    const curRow = locals[cdt][cdn]

    for (const row of frm.doc.installments) {
        if (curRow.disbursement_number != row.disbursement_number || row.name == curRow.name) {
            continue
        }
        frappe.throw(`<b>No Pencairan: ${curRow.disbursement_number}</b> digunakan di <b>Angsuran Row ${row.idx}</b>`)
    }

    let month = parseInt(curRow.disbursement_number.substr(12))
    frappe.model.set_value(cdt, cdn, 'installment_month', month)
    frm.refresh_field("installments")
}

function calculateScheduleLoan(frm) {
    if (!frm.doc.availability_period || !frm.doc.grace_period || !frm.doc.actual_number_of_payments) {
        return
    }
    let ano_payments = frm.doc.actual_number_of_payments;
    let grace_period = frm.doc.grace_period;
    let availibiltyPeriod = frm.doc.availability_period;

    let scheduleNumberOfPayments = ano_payments - grace_period;
    let loanLengthInYears = scheduleNumberOfPayments/availibiltyPeriod;
    
    frm.set_value('scheduled_number_of_payments', scheduleNumberOfPayments);
    frm.set_value('loan_length_in_years', loanLengthInYears);
    frm.refresh_field('scheduled_number_of_payments');
    frm.refresh_field('loan_length_in_years');
}

function totalAmountDisbursement(frm, cdt, cdn) {
    const curRow = locals[cdt][cdn];
    let total = 0;
    
    if (curRow.idx == 1) {
        total += curRow.disbursement_amount
    } else {
        for (const row of frm.doc.disbursements) {
            if (curRow.idx > row.idx) {
                total += row.disbursement_amount
            }
        }
    }
    
    frappe.model.set_value(cdt, cdn, 'disbursement_total', total)
    frm.refresh_field('disbursements')
    
}

function checkGracePrincipal(frm, cdt, cdn) {
    let gracePeriod = frm.doc.grace_period;
    const curRow = locals[cdt][cdn]
    if (curRow.idx > gracePeriod) {
        let scheduleNumberOfPayments = frm.doc.scheduled_number_of_payments;
        let pricipalAmount = curRow.disbursement_total /  scheduleNumberOfPayments
        frappe.model.set_value(cdt, cdn, 'principal', pricipalAmount)
        frm.refresh_field('installments')
        calculateInterestAmount(frm, cdt, cdn)
    }else{
        frappe.model.set_value(cdt, cdn, 'principal', 0)
        frm.refresh_field('installments')
    }
}

function getDaysInstallment(frm, cdt, cdn) {
    const curRow = locals[cdt][cdn];
    const startDate = curRow.disbursement_date;
    const endDate = curRow.payment_date;

    if (!startDate || !endDate) {
        return;
    }
    const days = frappe.datetime.get_day_diff(endDate, startDate)

    frappe.model.set_value(cdt, cdn, 'days', days)
    frm.refresh_field('installments')
    calculateInterestAmount(frm, cdt, cdn)
}

function calculateInterestAmount(frm, cdt, cdn) {
    const curRow = locals[cdt][cdn];
    if (!curRow.loan_interest || !curRow.days) {
        return
    }
    let interestAmount = curRow.disbursement_total * curRow.loan_interest * curRow.days / frm.doc.days_in_year
    let paymentTotal = curRow.principal || 0 + interestAmount
    frappe.model.set_value(cdt, cdn, 'interest_amount', interestAmount)
    frappe.model.set_value(cdt, cdn, 'payment_total', paymentTotal)
    frm.refresh_field("installments")
}

let editId = null;
function showInterestRateDialog(frm) {
    let d = new frappe.ui.Dialog({
        title: "Suku Bunga",
        fields: [
            { fieldname: "loan_bank", fieldtype: "Link", label: "No Transaksi", reqd: 1, options: "Loan Bank", read_only:1},
            { fieldname: "bank", fieldtype: "Link", label: "Bank", read_only: 1, options: "Bank", read_only:1 },
            { fieldname: "date", fieldtype: "Date", label: "Tanggal" },
            { fieldname: "interest", fieldtype: "Percent", label: "Nilai (%)" },
            { fieldname: "simpan", fieldtype: "Button", label: "Simpan", click: () => saveInterest(d)},
            { fieldname: "list_data_html", fieldtype: "HTML" },
        ]
    });
    d.set_value("loan_bank", frm.doc.name);
    d.set_value("bank", frm.doc.bank);

    loadInterestList(frm.doc.name, d)

    d.show();
}


function renderInterestTable(dialog, rows) {
    let html = `
        <table class="table table-bordered" style="font-size:12px;">
            <thead>
                <tr>
                    <th>No.</th>
                    <th>Tanggal</th>
                    <th>Bank</th>
                    <th>Nilai (%)</th>
                    <th>Aksi</th>
                </tr>
            </thead>
            <tbody>
                ${
                    rows.length === 0
                    ? `<tr><td colspan="5" class="text-center">Tidak ada data</td></tr>`
                    : rows.map((row, i) => `
                        <tr>
                            <td>${i+1}</td>
                            <td>${frappe.datetime.str_to_user(row.date)}</td>
                            <td>${row.bank}</td>
                            <td>${row.interest}</td>
                            <td>
                                <a class="btn btn-warning btn-xs btn-edit" data-name="${row.name}">Edit</a>
                            </td>
                        </tr>
                    `).join("")
                }
            </tbody>
        </table>
    `;

    dialog.fields_dict.list_data_html.$wrapper.html(html);
    dialog.fields_dict.list_data_html.$wrapper.on('click', '.btn-edit', function() {
        const name = $(this).data('name');
        editInterest(name);
        console.log(name);
        
    });
}


function loadInterestList(loan_bank, dialog) {
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Loan Bank Interest",
            fields: ["name", "date", "bank", "interest"],
            filters: {
                loan_bank: loan_bank
            },
            order_by: "date asc"
        },
        callback: function(r) {
            if (r.message) {
                renderInterestTable(dialog, r.message);
            }
        }
    });
}

function saveInterest(dialog) {
    const values = dialog.get_values();
    if (!values) return;

    const payload = {
        doctype: "Loan Bank Interest",
        loan_bank: values.loan_bank,
        bank: values.bank,
        date: values.date,
        interest: values.interest
    };

    const method = editId ? "sth.finance_sth.doctype.loan_bank.loan_bank.update_loan_bank_interest" : "frappe.client.insert";
    if (editId) payload.name = editId;

    frappe.call({
        method,
        args: { doc: payload },
        callback: () => {
            frappe.show_alert(editId ? "Perubahan disimpan" : "Data disimpan");

            loadInterestList(values.loan_bank, dialog);

            editId = null;
            dialog.set_value("date", null);
            dialog.set_value("interest", null);
        }
    });
}

function editInterest(name) {
    editId = name;

    frappe.call({
        method: "frappe.client.get",
        args: { doctype: "Loan Bank Interest", name },
        callback: (r) => {
            const doc = r.message;
            const d = cur_dialog;

            d.set_value("date", doc.date);
            d.set_value("interest", doc.interest);

            loadInterestList(doc.loan_bank, d);
        }
    });
}

function getLastInterest(frm, cdt, cdn) {
    if (!locals[cdt][cdn].payment_date) {
        
    }
    frappe.call({
        method: "sth.finance_sth.doctype.loan_bank.loan_bank.get_last_interest",
        args: {
            loan_bank: frm.doc.name,
            date: locals[cdt][cdn].payment_date
        },
        freeze: true,
        callback: (r) => {
            if (r.message) {
                frappe.model.set_value(cdt, cdn, "loan_interest", r.message)
                frm.refresh_field('installments')
            }
        },
        error: (r) => {
            console.log(r);
        
        }
    })
}

function filterDisbursementNumber(frm, cdt, cdn) {
    if (frm.is_new()) {
        return
    }
    frm.fields_dict.installments.grid.get_field('disbursement_number').get_query = (doc, cdt, cdn) => {
        return {
            filters : {
                reference_name: frm.doc.name
            }
        }
    }
}

async function hideShowAngsuran(frm) {
    const resp = await frappe.db.get_list("Disbursement Loan", {
        filters: { reference_name: frm.doc.name }
    });

    const check = resp.length > 0;

    frm.toggle_display("installments", check);
}

function filterUnit(frm) {
    frm.set_query('unit', (doc) => {
        return {
            filters: {
                "company": ["=", doc.company]
            }
        }
    })
}

function filterAccounting(frm) {
    frm.set_query('installment_credit_to', (doc) => {
        return {
            filters: {
                account_type: "Payable",
                company: ["=", doc.company],
                is_group: 0
            }
        }
    })
    frm.set_query('disbursement_debit_to', (doc) => {
        return {
            filters: {
                account_type: "Receivable",
                company: ["=", doc.company],
                is_group: 0
            }
        }
    })
    frm.set_query('installment_debit_to', (doc) => {
        return {
            filters: {
                company: ["=", doc.company],
                is_group: 0
            }
        }
    })
    frm.set_query('expense_account', (doc) => {
        return {
            filters: {
                company: ["=", doc.company],
                is_group: 0
            }
        }
    })
}