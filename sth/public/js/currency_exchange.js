frappe.ui.form.on("Currency Exchange", {
    refresh(frm){
        hideField(frm);
        frm.set_value('to_currency', "IDR");
    },
    buying_rate(frm){
        calculateMiddleRate(frm)
    },
    selling_rate(frm){
        calculateMiddleRate(frm)
    },
})

function hideField(frm) {
    const fields = ["for_buying", "for_selling", "to_currency"];
    for (const field of fields) {
        frm.toggle_display(field, false);
    }
}

function calculateMiddleRate(frm) {
    const middleRate = (frm.doc.buying_rate + frm.doc.selling_rate) / 2
    frm.set_value('exchange_rate', middleRate)
    frm.refresh_field('exchange_rate')
}