// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.provide("sth.queries")
frappe.ui.form.on("Berita Acara", {
    onload(frm) {
        frm.set_query("item_code", "table_klkc", sth.queries.item_by_subtype)
    },

    refresh(frm) {
        if (frm.doc.docstatus == 1) {
            frm.add_custom_button("Material Request", function () {
                frappe.model.open_mapped_doc({
                    method: frappe.model.get_server_module_name(frm.doctype) + ".create_mr",
                    frm,
                    run_link_triggers: 1
                })
            }, __("Create"))
        }

        if (frm.is_new()) {
            frm.set_value("make", frappe.session.user)
        }

        frm.fields_dict.table_klkc.grid.update_docfield_property(
            "kendaraan",
            "read_only",
            frm.doc.asset
        );
        frm.fields_dict.table_klkc.grid.update_docfield_property(
            "harga_satuan",
            "read_only",
            !frm.doc.asset
        );
    },

    unit(frm) {
        frm.doc.table_klkc.forEach((row) => {
            get_stock_item(row.item_code, frm.doc.unit).then((res) => {
                frappe.model.set_value(row.doctype, row.name, "stock", res)
            })
        })

        frm.refresh_field('table_klkc')
    },

    sub_purchase_type(frm) {
        if (!frm.doc.sub_purchase_type || frm.doc.sub_purchase_type != "Purchase Request") {
            frm.set_value("asset", 0)
        }
    },

    asset(frm) {
        frm.fields_dict.table_klkc.grid.update_docfield_property(
            "kendaraan",
            "read_only",
            frm.doc.asset
        );
        frm.fields_dict.table_klkc.grid.update_docfield_property(
            "harga_satuan",
            "read_only",
            !frm.doc.asset
        );
        // console.log(frm.doc.asset);
    }
});

frappe.ui.form.on("Berita Acara Detail", {
    form_render(frm, dt, dn) {
        frm.get_field('table_klkc').$wrapper.find(".grid-duplicate-row").off("click")
    },

    item_code(frm, dt, dn) {
        let row = locals[dt][dn]
        let exist = frm.doc.table_klkc.find((data) => row.item_code == data.item_code && row.idx != data.idx)
        if (exist) {
            frappe.msgprint("Item code sudah terdaftar dalam tabel.")
            frappe.model.clear_doc(row.doctype, row.name)
            refresh_field("table_klkc")
            frappe.dom.unfreeze()
        }

        get_stock_item(row.item_code, frm.doc.unit).then((res) => {
            frappe.model.set_value(dt, dn, "stock", res)
        })
    },
    jumlah(frm, dt, dn) {
        calculate_total(frm, dt, dn)
    },
    harga_satuan(frm, dt, dn) {
        calculate_total(frm, dt, dn)
    }
})

function get_stock_item(item_code = "", unit = "") {
    const method = frappe.model.get_server_module_name(cur_frm.doctype) + ".get_stock_item"

    return new Promise((resolve, reject) => {
        frappe.xcall(method, { item_code, unit }).then((res) => {
            resolve(res)
        })
    })
}

function calculate_total(frm, dt, dn) {
    let row = locals[dt][dn]
    let total = row.jumlah * row.harga_satuan

    frappe.model.set_value(dt, dn, "total", total)

    frm.set_value("subtotal", frm.doc.table_klkc.reduce((acc, row) => acc + row.total, 0))
}