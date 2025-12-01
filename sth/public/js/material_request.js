frappe.provide("sth.queries")

frappe.ui.form.on("Material Request", {
    refresh(frm) {
        frm.set_query("item_code", "items", sth.queries.item_by_subtype)
        if (frm.doc.docstatus != 1) {
            frm.add_custom_button("Berita Acara", function () {
                console.log("Oke");

            }, __("Get Items From"))
        }
    },
});