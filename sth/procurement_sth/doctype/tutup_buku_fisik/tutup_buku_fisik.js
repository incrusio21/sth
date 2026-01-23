// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Tutup Buku Fisik", {
    setup(frm) {
        frm.set_query("warehouse", "list_gudang", (doc) => {
            return {
                filters: {
                    company: doc.company,
                    is_group: 0
                }
            }
        })
    },

    refresh(frm) {
        if (frm.doc.docstatus == 1) {
            frm.add_custom_button("Open", function () {
                const method = frappe.model.get_server_module_name(frm.doctype) + ".open_doc"

                frappe.confirm("Apakah anda yakin ingin membuka document ini ? ",
                    () => {
                        frappe.xcall(method, { name: frm.docname }).then(() => {
                            frm.reload_doc()
                        })
                    }
                )
            })
        }
    },

    periode(frm) {
        frm.trigger('set_start_end_dates')
    },

    set_start_end_dates(frm) {
        if (frm.doc.periode) {
            frappe.call({
                method: "hrms.payroll.doctype.payroll_entry.payroll_entry.get_start_end_dates",
                args: {
                    payroll_frequency: frm.doc.periode,
                    start_date: frm.doc.tanggal_dibuat,
                },
                callback: function (r) {
                    if (r.message) {
                        frm.set_value("from_date", r.message.start_date);
                        frm.set_value("to_date", r.message.end_date);
                    }
                },
            });
        }
    },

});

