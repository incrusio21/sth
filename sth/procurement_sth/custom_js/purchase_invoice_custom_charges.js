frappe.ui.form.on("Purchase Invoice", {
    refresh(frm) {
        frm.fields_dict["charges_purchase_invoice"].grid.update_docfield_property(
            "account", "get_query", function() {
                return {
                    filters: {
                        company: frm.doc.company,
                        is_group: 0
                    }
                };
            }
        );
    }
});

frappe.ui.form.on("Charges Purchase Invoice", {
    account(frm, cdt, cdn) {
        sync_charges_to_taxes(frm);
    },
    total(frm, cdt, cdn) {
        sync_charges_to_taxes(frm);
    },
    keterangan(frm, cdt, cdn) {
        sync_charges_to_taxes(frm);
    },
    charges_purchase_invoice_remove(frm) {
        sync_charges_to_taxes(frm);
    }
});

const CHARGES_MARKER = "__from_charges__";

function sync_charges_to_taxes(frm) {
    // Filter berdasarkan marker di description yang tersimpan ke DB
    frm.doc.taxes = (frm.doc.taxes || []).filter(
        row => !(row.description || "").startsWith(CHARGES_MARKER)
    );

    let total_charges = 0;

    (frm.doc.charges_purchase_invoice || []).forEach(charge => {
        if (!charge.account || !charge.total) return;

        total_charges += charge.total;

        let new_row = frm.add_child("taxes");
        new_row.charge_type = "Actual";
        new_row.category = "Total";
        new_row.account_head = charge.account;
        new_row.tax_amount = charge.total;
        new_row.description = `${CHARGES_MARKER}${charge.keterangan || ""}`;
    });

    frm.set_value("total_charges", total_charges);
    frm.refresh_field("taxes");
    frm.trigger("calculate_taxes_and_totals");
}