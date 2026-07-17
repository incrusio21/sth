// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

// Cache filter per baris: { [cdn]: { filters: {...} } }
const _row_account_filters = {};

// Cache filter kendaraan per baris, diisi berdasarkan Divisi dari sub_unit
const _row_kendaraan_filters = {};

frappe.ui.form.on("Permintaan Pengeluaran Barang", {
    setup(frm) {
        frm.set_query("gudang", function (doc) {
            return {
                filters: {
                    is_group: 0,
                    company: doc.pt_pemilik_barang,
                    central: true
                }
            }
        })

        frm.set_query("kode_barang", "items", function (doc) {
            return {
                query: "sth.controllers.queries.get_items_query",
            }
        })

        frm.set_query("project", "items", function (doc) {
            return {
                filters: {
                    supplier: doc.kontraktor
                }
            }
        })

        frm.set_query("sub_unit", "items", function (doc) {
            const query = frappe.model.get_server_module_name(doc.doctype) + ".filter_divisi"
            return {
                query,
                filters: {
                    warehouse: doc.gudang,
                }
            }
        })

        frm.set_query("blok", "items", function (doc, dt, dn) {
            const child = locals[dt][dn]
            return {
                filters: {
                    divisi: child.sub_unit,
                }
            }
        })

        frm.set_query("kendaraan", "items", function (doc, cdt, cdn) {
            const cached = _row_kendaraan_filters[cdn];
            return {
                filters: {
                    company: doc.pt_pemilik_barang,
                    ...(cached ? cached.filters : {}),
                }
            }
        })

        // Filter account per baris — membaca dari cache _row_account_filters
        frm.set_query("account", "items", function (doc, cdt, cdn) {
            const cached = _row_account_filters[cdn];
            if (cached) return cached;
            return {
                filters: {
                    company: doc.pt_pemilik_barang || undefined,
                    is_group: 0,
                },
            };
        })
    },

    refresh(frm) {
        if (frm.doc.docstatus == 1 && !["Barang Telah Dikeluarkan", "Closed"].includes(frm.doc.status)) {
            frm.add_custom_button("Closed", function () {
                frappe.confirm(
                    'Apakah anda yakin ingin menutup dokumen ini?',
                    () => {
                        const method = frappe.model.get_server_module_name(frm.doctype) + ".close_status"
                        frappe.xcall(method, { name: frm.docname }).then(() => {
                            frm.reload_doc()
                            frappe.show_alert({
                                message: __('Document has been closed'),
                                indicator: 'green'
                            });
                        })
                    },
                    null
                );
            })
        }

        if (!frm.is_new()) {
            if (frm.doc.persetujuan_1) {
                frm.set_df_property('persetujuan_1', 'read_only', 1);
            }
            if (frm.doc.persetujuan_2) {
                frm.set_df_property('persetujuan_2', 'read_only', 1);
            }
        }
    },

    pt_pemilik_barang(frm) {
        (frm.doc.items || []).forEach((row) => {
            resolve_account_filter(frm, row.doctype, row.name);
        });
    },

    onload(frm) {
        (frm.doc.items || []).forEach((row) => {
            resolve_account_filter(frm, row.doctype, row.name);
        });

        if (!frm.is_new()) {
            if (frm.doc.persetujuan_1) {
                frm.set_df_property('persetujuan_1', 'read_only', 1);
            }
            if (frm.doc.persetujuan_2) {
                frm.set_df_property('persetujuan_2', 'read_only', 1);
            }
        }
    },

    sub_unit(frm) {
        if (!frm.doc.sub_unit) return;
    },
});


frappe.ui.form.on('Permintaan Pengeluaran Barang Item', {

    kode_barang(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (frm.doc.gudang && row.kode_barang) {
            frappe.xcall("sth.api.get_stock_item", { item_code: row.kode_barang, warehouse: frm.doc.gudang })
                .then((res) => {
                    frappe.model.set_value(row.doctype, row.name, "jumlah_saat_ini", res || 0)
                })
        } else if (!frm.doc.gudang) {
            frappe.msgprint(__('Please select Gudang first'));
            frappe.model.set_value(cdt, cdn, 'kode_gudang', '');
        }
    },

    sub_unit(frm, cdt, cdn) {
        frappe.model.set_value(cdt, cdn, 'kendaraan', '');
        resolve_account_filter(frm, cdt, cdn);
        apply_divisi_rules(frm, cdt, cdn);
    },

    stasiun(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if ((row.sub_unit || "").trim().toUpperCase().includes("MILL")) {
            resolve_account_filter(frm, cdt, cdn);
        }
    },

    kegiatan(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        const sub_unit = (row.sub_unit || "").trim();
        if (!["MILL", "TRAKSI", "KANTOR"].includes(sub_unit)) {
            apply_account_filter_from_kegiatan(frm, cdt, cdn);
        }
    }
});


// ─── Helper: simpan filter prefix ke cache ────────────────────────────────────
function apply_account_filter_by_prefix(frm, cdt, cdn, prefix) {
    _row_account_filters[cdn] = {
        filters: {
            company: frm.doc.pt_pemilik_barang,
            account_number: ["like", prefix + "%"],
            is_group: 0,
        },
    };
    // frappe.model.set_value(cdt, cdn, "account", null);
    frappe.show_alert({
        message: __("Filter <b>Account</b> menampilkan semua akun berawalan <b>") + prefix + "</b>.",
        indicator: "blue",
    });
}


// ─── Helper: filter dari Kegiatan.items.account ───────────────────────────────
function apply_account_filter_from_kegiatan(frm, cdt, cdn) {
    const row = locals[cdt][cdn];

    if (!row.kegiatan) {
        _row_account_filters[cdn] = { filters: { is_group: 0, company: frm.doc.company } };
        // frappe.model.set_value(cdt, cdn, "account", null);
        return;
    }

    frappe.call({
        method: "frappe.client.get",
        args: { doctype: "Kegiatan", name: row.kegiatan },
        callback(r) {
            if (!r.message) {
                frappe.msgprint({ title: __("Error"), message: __("Data Kegiatan tidak ditemukan: ") + row.kegiatan, indicator: "red" });
                return;
            }

            const valid_accounts = [...new Set((r.message.items || []).map((i) => i.account).filter(Boolean))];

            if (!valid_accounts.length) {
                frappe.msgprint({ title: __("Perhatian"), message: __("Tidak ada <b>Account</b> yang dikonfigurasi pada Kegiatan <b>") + row.kegiatan + "</b>.", indicator: "orange" });
                return;
            }

            _row_account_filters[cdn] = {
                filters: { name: ["in", valid_accounts], is_group: 0 },
            };
            // frappe.model.set_value(cdt, cdn, "account", null);
            frappe.show_alert({ message: __("Filter <b>Account</b> diperbarui dari Kegiatan <b>") + row.kegiatan + "</b>.", indicator: "green" });
        },
    });
}


// ─── Helper: filter dari Station Master (MILL) ────────────────────────────────
function apply_account_filter_from_station(frm, cdt, cdn) {
    const row = locals[cdt][cdn];

    frappe.call({
        method: "frappe.client.get",
        args: { doctype: "Station Master", name: row.stasiun },
        callback(r) {
            if (!r.message) {
                frappe.msgprint({ title: __("Error"), message: __("Data Station Master tidak ditemukan untuk stasiun: ") + row.stasiun, indicator: "red" });
                return;
            }

            const procurement_settings = r.message.station_procurement_settings || [];
            if (!procurement_settings.length) {
                frappe.msgprint({ title: __("Perhatian"), message: __("Tidak ada <b>Station Procurement Settings</b> pada stasiun <b>") + row.stasiun + "</b>.", indicator: "orange" });
                return;
            }

            const valid_companies = [...new Set(procurement_settings.map((s) => s.company).filter(Boolean))];
            const valid_accounts = [...new Set(procurement_settings.map((s) => s.account).filter(Boolean))];

            if (!valid_accounts.length) {
                frappe.msgprint({ title: __("Perhatian"), message: __("Tidak ada <b>Account</b> di Station Procurement Settings stasiun <b>") + row.stasiun + "</b>.", indicator: "orange" });
                return;
            }

            let company_filter = valid_companies;
            if (frm.doc.pt_pemilik_barang) {
                if (valid_companies.includes(frm.doc.pt_pemilik_barang)) {
                    company_filter = [frm.doc.pt_pemilik_barang];
                } else {
                    frappe.msgprint({ title: __("Perhatian"), message: __("PT Pemilik Barang <b>") + frm.doc.pt_pemilik_barang + __("</b> tidak terdaftar di Station Procurement Settings stasiun <b>") + row.stasiun + "</b>.", indicator: "orange" });
                }
            }

            _row_account_filters[cdn] = {
                filters: { company: ["in", company_filter], parent_account: ["in", valid_accounts], is_group: 0 },
            };
            // frappe.model.set_value(cdt, cdn, "account", null);
            frappe.show_alert({ message: __("Filter <b>Account</b> diperbarui dari stasiun <b>") + row.stasiun + "</b>.", indicator: "green" });
        },
    });
}


// ─── Helper: toggle read_only kendaraan hanya untuk baris tertentu ───────────
function toggle_kendaraan_readonly(frm, cdn, read_only) {
    const grid_row = frm.fields_dict['items'].grid.grid_rows_by_docname[cdn];
    if (!grid_row) return;

    grid_row.toggle_editable('kendaraan', !read_only);

    // toggle_editable saja tidak selalu memicu re-render baris,
    // sehingga status read_only lama bisa "nempel" di DOM. Paksa refresh.
    if (typeof grid_row.refresh_field === 'function') {
        grid_row.refresh_field('kendaraan');
    } else {
        grid_row.refresh();
    }
}

// ─── Helper: terapkan aturan berdasarkan Divisi (mill/kantor/traksi/bengkel) ─
function apply_divisi_rules(frm, cdt, cdn) {
    const row = locals[cdt][cdn];

    delete _row_kendaraan_filters[cdn];
    toggle_kendaraan_readonly(frm, cdn, false);

    if (!row.sub_unit) return;

    frappe.db.get_value('Divisi', row.sub_unit, ['mill', 'kantor', 'traksi', 'bengkel'])
        .then(({ message }) => {
            if (!message) return;
            const { mill, kantor, traksi, bengkel } = message;

            if (mill && kantor) {
                frappe.model.set_value(cdt, cdn, 'tipe_asset', 'Asset');
                _row_kendaraan_filters[cdn] = { filters: { asset_category: 'MESIN-MESIN' } };
            } else if (traksi) {
                frappe.model.set_value(cdt, cdn, 'tipe_asset', 'Alat Berat Dan Kendaraan');
            }

            if (bengkel) {
                toggle_kendaraan_readonly(frm, cdn, true);
                apply_account_filter_by_account_number(frm, cdt, cdn, ['4111003', '4111004']);
            }
        });
}

// ─── Helper utama: tentukan filter berdasarkan sub_unit ──────────────────────
function resolve_account_filter(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    const sub_unit = (row.sub_unit || "").trim();
    if (sub_unit.includes("MILL")) {
        if (!row.stasiun) {
            apply_account_filter_by_prefix(frm, cdt, cdn, "72");
        } else {
            apply_account_filter_from_station(frm, cdt, cdn);
        }
    } else if (sub_unit.includes("TRAKSI")) {
       apply_account_filter_by_account_number(frm, cdt, cdn, ["4112003", "4112004"]);
    } else if (sub_unit === "KANTOR") {
        apply_account_filter_by_prefix(frm, cdt, cdn, "71");
    } else if (sub_unit === "BIBITAN") {
        apply_account_filter_from_bibitan_settings(frm, cdt, cdn);
    } else if (sub_unit.includes("BENGKEL")) {
        apply_account_filter_by_account_number(frm, cdt, cdn, ["4111003", "4111004"]);
    } else {
        apply_account_filter_from_kegiatan(frm, cdt, cdn);
    }
}

// ─── Helper: filter berdasarkan daftar account_number tetap ───────────────────
function apply_account_filter_by_account_number(frm, cdt, cdn, account_numbers) {
    _row_account_filters[cdn] = {
        filters: {
            company: frm.doc.pt_pemilik_barang,
            account_number: ["in", account_numbers],
            is_group: 0,
        },
    };
    frappe.show_alert({
        message: __("Filter <b>Account</b> menampilkan akun ") + account_numbers.join(", ") + ".",
        indicator: "blue",
    });
}

function apply_account_filter_from_bibitan_settings(frm, cdt, cdn) {
    frappe.call({
        method: 'sth.procurement_sth.doctype.permintaan_pengeluaran_barang.permintaan_pengeluaran_barang.get_akun_kredit_bibitan',
        args: { company: frm.doc.pt_pemilik_barang },
        callback: (r) => {
            if (r.message) {
                frappe.model.set_value(cdt, cdn, 'account', r.message);
            }
        }
    });
}

function apply_account_filter_from_traksi_settings(frm, cdt, cdn) {
    const row = locals[cdt][cdn];

    if (!row.kode_barang) {
        frappe.msgprint({ title: __("Perhatian"), message: __("Pilih <b>Kode Barang</b> terlebih dahulu."), indicator: "orange" });
        return;
    }

    frappe.call({
        method: "frappe.client.get",
        args: { doctype: "Item", name: row.kode_barang },
        callback(r) {
            if (!r.message) {
                frappe.msgprint({ title: __("Error"), message: __("Item tidak ditemukan: ") + row.kode_barang, indicator: "red" });
                return;
            }

            const item_group = r.message.kelompok_barang;
            if (!item_group) {
                frappe.msgprint({ title: __("Perhatian"), message: __("Item <b>") + row.kode_barang + __("</b> tidak memiliki Kelompok Barang."), indicator: "orange" });
                return;
            }

            frappe.call({
                method: "frappe.client.get",
                args: { doctype: "Item Group", name: item_group },
                callback(r2) {
                    if (!r2.message) {
                        frappe.msgprint({ title: __("Error"), message: __("Item Group tidak ditemukan: ") + item_group, indicator: "red" });
                        return;
                    }

                    const account_rows = (r2.message.kelompok_barang_account_pengeluaran_barang || []);
                    if (!account_rows.length) {
                        frappe.msgprint({ title: __("Perhatian"), message: __("Tidak ada <b>Account</b> di kelompok barang <b>") + item_group + "</b>.", indicator: "orange" });
                        return;
                    }

                    const company = frm.doc.pt_pemilik_barang;
                    const filtered = company
                        ? account_rows.filter((a) => a.company === company)
                        : account_rows;

                    if (!filtered.length) {
                        frappe.msgprint({ title: __("Perhatian"), message: __("Tidak ada <b>Account</b> untuk company <b>") + company + __("</b> di kelompok barang <b>") + item_group + "</b>.", indicator: "orange" });
                        return;
                    }

                    const valid_accounts = [...new Set(filtered.map((a) => a.account).filter(Boolean))];
                    if (!valid_accounts.length) {
                        frappe.msgprint({ title: __("Perhatian"), message: __("Tidak ada <b>Account</b> yang dikonfigurasi di kelompok barang <b>") + item_group + "</b>.", indicator: "orange" });
                        return;
                    }

                    _row_account_filters[cdn] = {
                        filters: { name: ["in", valid_accounts], is_group: 0 },
                    };
                    frappe.model.set_value(cdt, cdn, "account", valid_accounts[0]);
                    frappe.show_alert({ message: __("Account diisi dari kelompok barang <b>") + item_group + "</b>.", indicator: "green" });
                }
            });
        }
    });
}