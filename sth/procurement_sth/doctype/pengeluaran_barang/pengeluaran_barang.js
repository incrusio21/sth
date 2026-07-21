// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

// Cache filter per baris: { [cdn]: { filters: {...} } }
const _row_account_filters = {};

// Cache filter kendaraan per baris, diisi berdasarkan Divisi dari sub_unit
const _row_kendaraan_filters = {};

frappe.ui.form.on("Pengeluaran Barang", {

	setup(frm) {
		frm.set_query("no_permintaan_pengeluaran", function (doc) {
			return {
				filters: {
					pt_pemilik_barang: doc.pt_pemilik_barang,
					docstatus: 1,
					outgoing: ["<", 100],
					status: ["!=", "Closed"]
				}
			}
		})

		frm.set_query("gudang", function (doc) {
			return {
				filters: {
					is_group: 0,
					company: doc.pt_pemilik_barang
				}
			}
		})

		frm.set_query("sub_unit", "items", function (doc) {
			return {
				filters: {
					company: doc.pt_pemilik_barang
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

		frm.set_query("nama_penerima", function (doc) {
			return {
				filters: {
					unit: doc.unit,
				}
			}
		})

		// Filter account per baris — membaca dari cache _row_account_filters
		frm.set_query("account", "items", function (doc, cdt, cdn) {
			const cached = _row_account_filters[cdn];
			if (cached) return cached;
			// Fallback: hanya filter company + non-group
			return {
				filters: {
					company: doc.pt_pemilik_barang || undefined,
					is_group: 0,
				},
			};
		})
	},

	refresh(frm) {
		frm.set_df_property("items", "cannot_add_rows", true)
	},

	onload(frm) {
		(frm.doc.items || []).forEach((row) => {
			resolve_account_filter(frm, row.doctype, row.name);
			apply_divisi_rules(frm, row.doctype, row.name);
		});
	},

	no_permintaan_pengeluaran(frm) {
		if (!frm.doc.no_permintaan_pengeluaran) return;
		frm.call("set_items").then((res) => {
			if (res.message) {
				frappe.model.clear_table(frm.doc, "items")
				res.message.forEach((item) => {
					let row = frappe.model.add_child(frm.doc, "items")
					Object.assign(row, item)
				})
				frm.refresh_field("items")
			}
		})
	},
});


frappe.ui.form.on('Pengeluaran Barang Item', {

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
		frappe.model.set_value(cdt, cdn, 'cost_center', '');
		resolve_account_filter(frm, cdt, cdn);
		apply_divisi_rules(frm, cdt, cdn);
	},

	kendaraan(frm, cdt, cdn) {
		apply_km_from_kendaraan(frm, cdt, cdn);
	},

	stasiun(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if ((row.sub_unit || "").trim() == "MILL") {
			resolve_account_filter(frm, cdt, cdn);
		}
		apply_tipe_asset_mill_machine(frm, cdt, cdn);
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
		_row_account_filters[cdn] = { filters: { is_group: 0 } };
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


// ─── Helper: filter dari Procurement Settings > Sub Unit Traksi (TRAKSI) ─────
function apply_account_filter_from_traksi_settings(frm, cdt, cdn) {
	frappe.call({
		method: "frappe.client.get",
		args: { doctype: "Procurement Settings", name: "Procurement Settings" },
		callback(r) {
			if (!r.message) {
				frappe.msgprint({ title: __("Error"), message: __("Procurement Settings tidak ditemukan."), indicator: "red" });
				return;
			}

			const traksi_rows = (r.message.sub_unit_traksi_procurement_settings || []);
			if (!traksi_rows.length) {
				frappe.msgprint({ title: __("Perhatian"), message: __("Tidak ada konfigurasi <b>Sub Unit Traksi</b> di Procurement Settings."), indicator: "orange" });
				return;
			}

			const company = frm.doc.pt_pemilik_barang;
			const filtered = company
				? traksi_rows.filter((r) => r.company === company)
				: traksi_rows;

			if (!filtered.length) {
				frappe.msgprint({ title: __("Perhatian"), message: __("Tidak ada <b>Account</b> untuk company <b>") + company + __("</b> di Sub Unit Traksi Procurement Settings."), indicator: "orange" });
				return;
			}

			const valid_accounts = [...new Set(filtered.map((r) => r.account).filter(Boolean))];
			if (!valid_accounts.length) {
				frappe.msgprint({ title: __("Perhatian"), message: __("Tidak ada <b>Account</b> yang dikonfigurasi di Sub Unit Traksi Procurement Settings."), indicator: "orange" });
				return;
			}

			_row_account_filters[cdn] = {
				filters: { name: ["in", valid_accounts], is_group: 0 },
			};
			frappe.model.set_value(cdt, cdn, "account", valid_accounts[0]);
			frappe.show_alert({ message: __("Filter <b>Account</b> diperbarui dari Sub Unit Traksi Procurement Settings."), indicator: "green" });
		},
	});
}



// ─── Helper: filter dari Procurement Settings > Sub Unit Traksi (TRAKSI) ─────
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


// ─── Helper: simpan filter account berdasarkan daftar account_number tetap ───
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


// ─── Helper: tentukan tipe_asset & aturan kendaraan/account dari Divisi ──────
// mill=1 & kantor=1 → tipe_asset "Asset", kendaraan difilter asset_category = MESIN-MESIN
// traksi=1          → tipe_asset "Alat Berat Dan Kendaraan"
// bengkel=1         → kendaraan read only, account hanya 4111003 / 4111004
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

			apply_tipe_asset_mill_machine(frm, cdt, cdn);
		});

	apply_cost_center_from_divisi(frm, cdt, cdn);
}

// ─── Helper: isi KM/HM sesuai doctype target dari kendaraan (Dynamic Link) ───
// Tiap tipe_asset menyimpan KM/HM di field yang berbeda-beda:
// Alat Berat Dan Kendaraan → kmhm_akhir, Mill Machine → hour_meters, Asset → (belum ada).
const KM_FIELD_BY_TIPE_ASSET = {
	"Alat Berat Dan Kendaraan": "kmhm_akhir",
	"Mill Machine": "hour_meters",
};

function apply_km_from_kendaraan(frm, cdt, cdn) {
	const row = locals[cdt][cdn];

	if (!row.kendaraan || !row.tipe_asset) {
		frappe.model.set_value(cdt, cdn, 'km', 0);
		return;
	}

	const km_fieldname = KM_FIELD_BY_TIPE_ASSET[row.tipe_asset];
	if (!km_fieldname) {
		frappe.model.set_value(cdt, cdn, 'km', 0);
		return;
	}

	frappe.db.get_value(row.tipe_asset, row.kendaraan, km_fieldname)
		.then(({ message }) => {
			frappe.model.set_value(cdt, cdn, 'km', (message && message[km_fieldname]) || 0);
		});
}

// ─── Helper: sub_unit MILL + stasiun terisi → tipe_asset "Mill Machine" ──────
function apply_tipe_asset_mill_machine(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if ((row.sub_unit || "").trim() == "MILL" && row.stasiun) {
		frappe.model.set_value(cdt, cdn, 'tipe_asset', 'Mill Machine');
	}
}

// ─── Helper: isi Cost Center dari Divisi.cost_center, fallback ke UMUM ───────
// Hanya mengisi bila cost_center baris masih kosong — nilai spesifik dari
// kendaraan/blok/stasiun (lihat isi_cost_center di pengeluaran_barang.py)
// tetap jadi prioritas dan dihitung ulang saat dokumen disimpan.
function apply_cost_center_from_divisi(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row.sub_unit || row.cost_center) return;

	frappe.call({
		method: 'sth.procurement_sth.utils.get_cost_center_from_divisi',
		args: { sub_unit: row.sub_unit, company: frm.doc.pt_pemilik_barang },
		callback(r) {
			frappe.model.set_value(cdt, cdn, 'cost_center', r.message || '');
		},
	});
}


// ─── Helper utama: tentukan filter berdasarkan sub_unit ──────────────────────
function resolve_account_filter(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const sub_unit = (row.sub_unit || "").trim();

	if (sub_unit == "MILL") {
		if (!row.stasiun) {
			apply_account_filter_by_prefix(frm, cdt, cdn, "72");
		} else {
			apply_account_filter_from_station(frm, cdt, cdn);
		}
	} else if (sub_unit == "TRAKSI") {
		apply_account_filter_from_traksi_settings(frm, cdt, cdn);
	} else if (sub_unit == "KANTOR") {
		apply_account_filter_by_prefix(frm, cdt, cdn, "71");
	} else {
		apply_account_filter_from_kegiatan(frm, cdt, cdn);
	}
}


frappe.form.link_formatters['Item'] = function (value, doc) {
	return doc.item_name || doc.kode_barang
}