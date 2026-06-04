// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

// Cache filter per baris: { [cdn]: { filters: {...} } }
const _row_account_filters = {};

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

		frm.set_query("kendaraan", "items", function (doc) {
			return {
				filters: {
					company: doc.pt_pemilik_barang
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
		resolve_account_filter(frm, cdt, cdn);
	},

	stasiun(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if ((row.sub_unit || "").trim() == "MILL") {
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
			const valid_accounts  = [...new Set(procurement_settings.map((s) => s.account).filter(Boolean))];

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
				filters: { company: ["in", company_filter], name: ["in", valid_accounts], is_group: 0 },
			};
			frappe.model.set_value(cdt, cdn, "account", null);
			frappe.show_alert({ message: __("Filter <b>Account</b> diperbarui dari stasiun <b>") + row.stasiun + "</b>.", indicator: "green" });
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
		apply_account_filter_by_prefix(frm, cdt, cdn, "41120");
	} else if (sub_unit == "KANTOR") {
		apply_account_filter_by_prefix(frm, cdt, cdn, "71");
	} else {
		apply_account_filter_from_kegiatan(frm, cdt, cdn);
	}
}


frappe.form.link_formatters['Item'] = function (value, doc) {
	return doc.item_name || doc.kode_barang
}