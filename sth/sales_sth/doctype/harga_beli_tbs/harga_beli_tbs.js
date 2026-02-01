frappe.ui.form.on("Harga Beli TBS", {
    onload(frm) {
        frm.set_query("uom", () => {
            if (!frm.doc.item_code) return {};
            return {
                query: "sth.sales_sth.doctype.harga_beli_tbs.harga_beli_tbs.item_uom_query",
                filters: {
                    item_code: frm.doc.item_code
                }
            };
        });

        frm.set_query("supplier", () => {
            return {
                filters: {
                    is_supplier_tbs: 1
                }
            };
        });

        frappe.db.get_value("Item", frm.doc.item_code, "stock_uom")
        .then(r => {
            if (r.message?.stock_uom && !frm.doc.uom) {
                frm.set_value("uom", r.message.stock_uom);
            }
        });
    },
    refresh(frm){
        frm.disable_save();
        frm.events.load_price_history(frm);

        const grid = frm.fields_dict.price_change_history.grid;

        grid.cannot_add_rows = true;
        grid.wrapper.find('.grid-remove-rows').hide();
        grid.wrapper.find('.row-check').hide();
        grid.wrapper.find('.grid-add-row').hide();

        grid.refresh();
    },
    item_code(frm) {
        if (!frm.doc.item_code) {
            frm.set_value("uom", "");
            frm.clear_table("price_change_history");
            frm.refresh_field("price_change_history");
            return;
        }

        frappe.db.get_value("Item", frm.doc.item_code, "stock_uom")
            .then(r => {
                if (r.message?.stock_uom && !frm.doc.uom) {
                    frm.set_value("uom", r.message.stock_uom);
                }
            });

        frm.events.refresh_price_context(frm);
    },

    unit(frm) {
        frm.events.refresh_price_context(frm);
    },
    jarak(frm) {
        frm.events.refresh_price_context(frm);
    },
    supplier(frm) {
        frm.events.refresh_price_context(frm);
    },
    uom(frm) {
        frm.set_value("price_difference", 0);
        frm.events.refresh_price_context(frm);
    },

    refresh_price_context(frm) {
        frm.set_value("price_difference", 0);

        frm.events.fetch_current_price(frm);
        frm.events.load_price_history(frm);
    },

    fetch_current_price(frm) {
        if (!frm.doc.item_code || !frm.doc.unit || !frm.doc.uom) {
            frm.set_value("current_rate", 0);
            frm.set_value("last_update_on", "");
            frm.events.calculate_new_rate(frm);
            return;
        }

        const price_list = resolve_price_list(frm);

        frappe.call({
            method: "sth.sales_sth.doctype.harga_beli_tbs.harga_beli_tbs.get_current_price",
            args: {
                item_code: frm.doc.item_code,
                price_list: price_list,
                supplier: frm.doc.supplier,
                uom: frm.doc.uom
            },
            callback(r) {
                frm.set_value("current_rate", r.message?.rate || 0);
                frm.set_value("last_update_on", r.message?.modified || "");
                frm.events.calculate_new_rate(frm);
            }
        });
    },

    load_price_history(frm, after_load = null) {
        if (!frm.doc.item_code || !frm.doc.uom) {
            frm.clear_table("price_change_history");
            frm.refresh_field("price_change_history");
            return;
        }

        frappe.call({
            method: "sth.sales_sth.doctype.harga_beli_tbs.harga_beli_tbs.fetch_price_history",
            args: {
                item_code: frm.doc.item_code,
                // unit: frm.doc.unit,
                // jarak: frm.doc.jarak,
                // supplier: frm.doc.supplier,
                uom: frm.doc.uom
            },
            callback(r) {
                frm.clear_table("price_change_history");

                (r.message || []).forEach(row => {
                    let d = frm.add_child("price_change_history");
                    d.tanggal = row.effective_date;
                    d.old_price = row.old_price;
                    d.price_difference = row.price_difference;
                    d.new_price = row.new_price;
                    d.last_update = row.last_update;
                    d.status = row.status;
                    d.no_transaksi = row.no_transaksi;
                    d.unit = row.unit;
                    d.supplier = row.supplier;
                    d.approver = row.approver;
                    d.jarak = row.jarak;
                });

                frm.refresh_field("price_change_history");
            }
        });
    },
    price_difference(frm) {
        let rounded = Math.round(frm.doc.price_difference / 5) * 5;
        frm.set_value("price_difference", rounded);
        frm.events.calculate_new_rate(frm);
    },
    calculate_new_rate(frm) {
        const current = frm.doc.current_rate || 0;
        const diff = frm.doc.price_difference || 0;
        frm.set_value("new_rate", current + diff);
    },
    apply_price_change(frm) {
        if (!frm.doc.item_code || !frm.doc.unit || !frm.doc.uom ) {
            frappe.msgprint("Unit wajib diisi");
            return;
        }

        if (!frm.doc.price_difference) {
            frappe.msgprint("Price Difference tidak boleh 0");
            return;
        }

        frappe.confirm(
            `Apply perubahan harga menjadi ${frm.doc.new_rate}?`,
            () => {
                frappe.call({
                    method: "sth.sales_sth.doctype.harga_beli_tbs.harga_beli_tbs.create_price_note_from_harga_beli_tbs",
                    args: {
                        item_code: frm.doc.item_code,
                        unit: frm.doc.unit,
                        supplier: frm.doc.supplier,
                        jarak: frm.doc.jarak,
                        uom: frm.doc.uom,
                        current_rate: frm.doc.current_rate,
                        price_difference: frm.doc.price_difference,
                        remark: frm.doc.remark
                    },
                    freeze: true,
                    callback(r) {
                        frappe.show_alert("Request perubahan harga berhasil dibuat dan menunggu approval");

                        frm.set_value("price_difference", 0);
                        frm.set_value("remark", "");

                        frm.events.refresh_price_context(frm);

                        frm.events.load_price_history(frm, () => {
                            if (frm.is_dirty()) {
                                frm.save();
                            }
                        });
                    }
                });
            }
        );
    }

});

function resolve_price_list(frm) {
    if (!frm.doc.unit) return "";

    const jarak = frm.doc.jarak || "RING 1";
    return `${frm.doc.unit} - ${jarak}`;
}


frappe.ui.form.on("Item Price Control History TBS", {
    approve_btn(frm, cdt, cdn) {
        const can_approve = frappe.user.has_role("Administrator");

        if (!can_approve) {
            frappe.msgprint({
                title: "Akses Ditolak",
                message: "Anda tidak memiliki hak untuk melakukan approval harga.",
                indicator: "red"
            });
            return;
        }

        const row = locals[cdt][cdn];

        if (!row.no_transaksi) {
            frappe.msgprint({
                title: "Data Tidak Lengkap",
                message: "No Transaksi tidak ditemukan.",
                indicator: "orange"
            });
            return;
        }

        if (row.status == "Approved") {
            frappe.msgprint({
                title: "Harga Sudah Di Approve",
                message: "Harga Sudah Di Approve",
                indicator: "orange"
            });
            return;
        }

        frappe.confirm(
            "Approve perubahan harga ini?",
            () => {
                frappe.call({
                    method: "sth.sales_sth.doctype.harga_beli_tbs.harga_beli_tbs.approve_price_change",
                    args: {
                        ledger_name: row.no_transaksi
                    },
                    freeze: true,
                    callback() {
                        frappe.show_alert(
                            { message: "Harga berhasil di-approve", indicator: "green" },
                            5
                        );

                        frm.set_value("price_difference", 0);
                        frm.set_value("remark", "");

                        frm.events.refresh_price_context(frm);

                        frm.events.load_price_history(frm, () => {
                            if (frm.is_dirty()) {
                                frm.save();
                            }
                        });
                    }
                });
            }
        );
    }
});
