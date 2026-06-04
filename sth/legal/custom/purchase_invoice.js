// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Invoice", {
    refresh(frm) {
        if (frm.doc.docstatus == 0) {
            frm.add_custom_button(
                __("BAPP"),
                function () {
                    const _orig = frappe.call.bind(frappe);

                    frappe.call = function (opts, ...rest) {
                        if (
                            opts?.method === "frappe.model.mapper.map_docs" &&
                            opts?.args?.method?.includes("make_purchase_invoice")
                        ) {
                            const _cb = opts.callback;
                            opts.callback = (r) => {
                                frappe.call = _orig;
                                _cb && _cb(r);
                                const source_names = opts.args?.source_names || [];
                                if (source_names.length) {
                                    show_pb_dialog(frm, source_names[0]);
                                }
                            };
                            return _orig(opts);
                        }

                        return _orig(opts, ...rest);
                    };

                    erpnext.utils.map_current_doc({
                        method: "sth.legal.doctype.bapp.bapp.make_purchase_invoice",
                        source_doctype: "BAPP",
                        target: frm,
                        setters: {
                            supplier: frm.doc.supplier || undefined,
                            posting_date: undefined,
                        },
                        get_query_filters: {
                            docstatus: 1,
                            status: ["not in", ["Closed", "Completed", "Return Issued"]],
                            company: frm.doc.company,
                        },
                    });
                },
                __("Get Items From")
            );
        }
    },
});

function show_pb_dialog(frm, bapp) {
    frappe.call({
        method: "sth.legal.doctype.bapp.bapp.get_unclaimed_pengeluaran_barang_items",
        args: { bapp },
        callback(r) {
            const items = r.message || [];
            if (!items.length) return;

            const fmt = (val) => frappe.format(val, { fieldtype: "Currency" });

            const rows = items
                .map(
                    (item, idx) => `
                    <tr>
                        <td class="text-center">
                            <input type="checkbox" class="pb-check" data-idx="${idx}" checked />
                        </td>
                        <td>${item.kode_barang}</td>
                        <td>${item.item_name}</td>
                        <td class="text-right">${item.jumlah} ${item.satuan || ""}</td>
                        <td class="text-right">${fmt(item.rate)}</td>
                        <td class="text-right">${fmt(item.amount)}</td>
                    </tr>`
                )
                .join("");

            const d = new frappe.ui.Dialog({
                title: __("Pengeluaran Barang Belum Ditagihkan"),
                fields: [
                    {
                        fieldtype: "HTML",
                        options: `
                            <div style="overflow-x:auto">
                                <table class="table table-bordered table-condensed" style="font-size:12px">
                                    <thead class="grid-heading-row">
                                        <tr>
                                            <th style="width:40px">
                                                <input type="checkbox" id="pb-check-all" checked />
                                            </th>
                                            <th>Kode Barang</th>
                                            <th>Nama Barang</th>
                                            <th class="text-right">Qty</th>
                                            <th class="text-right">Rate</th>
                                            <th class="text-right">Amount</th>
                                        </tr>
                                    </thead>
                                    <tbody>${rows}</tbody>
                                </table>
                            </div>`,
                    },
                ],
                primary_action_label: __("Tambahkan"),
                primary_action() {
                    const selected = [];
                    d.$wrapper.find(".pb-check:checked").each(function () {
                        selected.push(items[parseInt($(this).data("idx"))]);
                    });

                    if (!selected.length) {
                        frappe.msgprint(__("Pilih minimal satu item."));
                        return;
                    }

                    selected.forEach((item) => {
                        const row = frm.add_child("purchase_invoice_pengeluaran_barang");
                        row.kode_barang = item.kode_barang;
                        row.nama_barang = item.item_name;
                        row.qty = item.jumlah;
                        row.rate = item.rate;
                        row.amount = item.amount;
                        row.account = item.account;
                        row.pengeluaran_barang_item = item.name;
                    });

                    frm.refresh_field("purchase_invoice_pengeluaran_barang");
                    d.hide();
                },
            });

            d.show();

            d.$wrapper.find("#pb-check-all").on("change", function () {
                d.$wrapper.find(".pb-check").prop("checked", this.checked);
            });
        },
    });
}