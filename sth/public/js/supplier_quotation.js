frappe.ui.form.on("Supplier Quotation", {
    onload(frm) {
        let original_refresh = frm.cscript.refresh;

        frm.cscript.refresh = function () {
            original_refresh.apply(this, arguments);
            frm.remove_custom_button("Material Request", "Get Items From")
            frm.remove_custom_button("Request for Quotation", "Get Items From")
            if (frm.doc.docstatus === 0) {
                btn_get_material_request(frm)
                btn_get_rfq(frm)
            }
        };
    },
    refresh(frm) {
        frm.page.btn_secondary.hide()
        if (frm.doc.workflow_state == "Approved") {
            frm.add_custom_button(__("Re open"), function () {
                let rfq = frm.doc.items[0].request_for_quotation
                frappe.xcall("sth.custom.supplier_quotation.reopen_rfq", { name: rfq, freeze: true })
                    .then((res) => {
                        // console.log("Oke")
                        frm.reload_doc()
                    })
            })

        } else {
            frm.remove_custom_button(__("Re open"))
        }
    }
})

function btn_get_material_request(frm) {
    frm.add_custom_button(
        __("Material Request"),
        function () {
            const d = erpnext.utils.map_current_doc({
                // method: "erpnext.stock.doctype.material_request.material_request.make_supplier_quotation",
                method: "sth.overrides.material_request.make_supplier_quotation",
                source_doctype: "Material Request",
                target: frm,
                allow_child_item_selection: 1,
                child_fieldname: "items",
                child_columns: ["item_code", "item_name", "qty", "uom", "unit"],
                size: "extra-large",
                setters: {
                    unit: undefined,
                },
                get_query_filters: {
                    material_request_type: "Purchase",
                    docstatus: 1,
                    status: ["!=", "Stopped"],
                    per_ordered: ["<", 100],
                    company: frm.doc.company,
                },
            });

            setTimeout(() => {
                // console.log(d.dialog);
                d.dialog.set_value("allow_child_item_selection", 1)
            }, 300);

        },
        __("Get Items From")
    );
}

function btn_get_rfq(frm) {
    frm.add_custom_button(
        __("Request for Quotation"),
        function () {
            if (!frm.doc.supplier) {
                frappe.throw({ message: __("Please select a Supplier"), title: __("Mandatory") });
            }
            const d = erpnext.utils.map_current_doc({
                // method: "erpnext.buying.doctype.request_for_quotation.request_for_quotation.make_supplier_quotation_from_rfq",
                method: "sth.overrides.request_for_quotation.make_supplier_quotation_from_rfq",
                source_doctype: "Request for Quotation",
                target: frm,
                allow_child_item_selection: 1,
                child_fieldname: "items",
                child_columns: ["item_code", "item_name", "qty", "uom", "unit"],
                size: "extra-large",
                setters: {
                    transaction_date: null,
                    unit: undefined,
                },
                get_query_filters: {
                    supplier: frm.doc.supplier,
                    company: frm.doc.company,
                },
                get_query_method:
                    "erpnext.buying.doctype.request_for_quotation.request_for_quotation.get_rfq_containing_supplier",
            });

            setTimeout(() => {
                // console.log(d.dialog);
                d.dialog.set_value("allow_child_item_selection", 1)
            }, 300);
        },
        __("Get Items From")
    );
}