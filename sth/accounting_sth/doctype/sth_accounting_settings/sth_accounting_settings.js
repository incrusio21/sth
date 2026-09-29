// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("STH Accounting Settings", {
	refresh(frm) {
		set_account_filters(frm)
	},
});

// Field Account dan Cost Center tiap tabel, semuanya disaring ke company
// barisnya. Kepala Akun Biaya KUD hanya akun grup, karena yang dinolkan akun
// turunannya. Sumber Biaya COGS boleh keduanya (`is_group: null`): akun grup
// ikut menjumlah turunannya. Tabel lain dipakai langsung untuk GL Entry, jadi
// harus akun (dan cost center) non grup.
const FILTER_TABEL = {
	sth_accounting_settings_payroll: { account: ["account"] },
	sth_accounting_settings_alokasi_gaji_bengkel: { account: ["account"] },
	sth_accounting_settings_reparasi_bengkel_account: { account: ["account"] },
	sth_accounting_settings_biaya_bengkel_dialokasi: { account: ["account"] },
	sth_accounting_settings_penjualan_asset: { account: ["piutang_account", "expense_account"] },
	sth_accounting_settings_cogs: {
		account: [
			"akun_persediaan_tbs",
			"akun_persediaan_cpo",
			"akun_persediaan_pk",
			"akun_alokasi_kebun",
			"akun_alokasi_pabrik",
			"akun_hpp_tbs",
			"akun_hpp_cpo",
			"akun_hpp_pk",
			"akun_selisih_rekonsiliasi",
		],
		cost_center: ["cost_center_kebun", "cost_center_mill"],
	},
	sth_accounting_settings_cogs_sumber_biaya: { account: ["akun"], is_group: null },
	sth_accounting_settings_kud: {
		account: [
			"akun_pembelian_tbs",
			"akun_management_fee",
			"akun_pph22",
			"akun_hutang_plasma_antara",
			"akun_lain_lain",
			"akun_hutang_mitra",
		],
		cost_center: ["cost_center"],
	},
	sth_accounting_settings_kud_mitra: { account: ["akun_piutang_plasma"] },
	sth_accounting_settings_kud_kepala_akun: { account: ["kepala_akun"], is_group: 1 },
};

function set_account_filters(frm) {
	Object.entries(FILTER_TABEL).forEach(([tabel, aturan]) => {
		const fieldnames = [...(aturan.account || []), ...(aturan.cost_center || [])];

		fieldnames.forEach((fieldname) => {
			// Cost center selalu non grup: dipakai langsung di GL Entry. Akun
			// ikut aturan tabelnya, bawaannya non grup; null berarti bebas.
			const is_group = (aturan.account || []).includes(fieldname)
				? aturan.is_group === undefined ? 0 : aturan.is_group
				: 0;

			frm.set_query(fieldname, tabel, function (doc, cdt, cdn) {
				const row = locals[cdt][cdn];
				const filters = { company: row.company };
				if (is_group !== null) filters.is_group = is_group;

				return { filters };
			});
		});
	});
}
