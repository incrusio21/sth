// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Invoice", {
    refresh(frm) {
        if(frm.doc.docstatus == 0){
            frm.add_custom_button(
                __("Pengakuan Pembelian TBS"),
                function () {
                    erpnext.utils.map_current_doc({
                        method: "sth.sales_sth.doctype.pengakuan_pembelian_tbs.pengakuan_pembelian_tbs.make_purchase_invoice",
                        source_doctype: "Pengakuan Pembelian TBS",
                        target: frm,
                        setters: {
                            nama_supplier: frm.doc.supplier || undefined,
                            unit: frm.doc.unit || undefined,
                            tanggal: undefined,
                        },
                        get_query_filters: {
                            docstatus: 1,
                            nama_supplier: frm.doc.supplier,
                            unit: frm.doc.unit,
                        },
                    });
                },
                __("Get Items From")
            );
        }
    },
})