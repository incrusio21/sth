// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Loan Bank", {
	refresh(frm) {
        filterBankAccount(frm);
        filterAccountCreditTo(frm);
        showInterestRateDialog(frm);
	},
});

function filterBankAccount(frm) {
    frm.set_query('bank_account', () => {
        return{
            filters: {
                bank: frm.doc.bank
            }
        }
    })
}

function filterAccountCreditTo(frm) {
    frm.set_query('credit_to', () => {
        return{
            filters: {
                account_type: "Payable"
            }
        }
    })
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
            order_by: "date desc"
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
        loan_bank: values.loanBank,
        bank: values.bank,
        date: values.date,
        interest: values.interest
    };

    const method = editId ? "frappe.client.save" : "frappe.client.insert";
    if (editId) payload.name = editId;

    frappe.call({
        method,
        args: { doc: payload },
        callback: () => {
            frappe.show_alert(editId ? "Perubahan disimpan" : "Data disimpan");

            loadInterestList(values.loanBank, dialog);

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