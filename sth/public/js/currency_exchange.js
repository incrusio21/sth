frappe.ui.form.on("Currency Exchange", {
    refresh(frm){
        hideField(frm);
        frm.set_value('to_currency', "IDR");
    }
})

function hideField(frm) {
    const fields = ["for_buying", "for_selling", "to_currency"];
    for (const field of fields) {
        frm.toggle_display(field, false);
    }
}