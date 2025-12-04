// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Deposito", {
	refresh(frm) {
        filterBankAccount(frm)
	},
    no_bilyet(frm){
        numberInput(frm, "no_bilyet")
    },
    periode_penempatan_bilyet(frm){
        calculateTotalHari(frm);
    }
});

function filterBankAccount(frm) {
    frm.set_query("nama_bank", (doc)=>{
        return {
            filters: {
                "company": ["=", doc.company]
            }
        }
    })
}

function numberInput(frm, fieldname) {
    let val = frm.doc[fieldname];

    if (val && /[^0-9]/.test(val)) {
        frm.set_value(fieldname, val.replace(/[^0-9]/g, ""));
        frm.refresh_field(fieldname)
    }
}

const periodPenempatanBilyet = {
    "1 Bulan": 30,
    "3 Bulan": 90,
    "6 Bulan": 180,
    "1 Tahun": 360,
    "3 Tahun": 1080,
    "5 Tahun": 1800
}

function calculateTotalHari(frm) {
    const periodBilyet = frm.doc.periode_penempatan_bilyet
    const totalHari = periodPenempatanBilyet[periodBilyet]
    const maturityDate = frappe.datetime.add_days(frm.doc.tanggal_valuta, totalHari)

    frm.set_value("total_hari", totalHari)
    frm.set_value("tanggal_jatuh_tempo_seharusnya", maturityDate)

    frm.refresh_field("total_hari")
    frm.refresh_field("tanggal_jatuh_tempo_seharusnya")
}