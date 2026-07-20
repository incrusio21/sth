// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Blok", {
	refresh(frm) {
		frm.set_query("status", function() {
			return {
				filters: {
					is_perawatan: 1
				}
			};
		});

		set_account_tbm_query(frm);

		if (frm.doc.workflow_state === "TBM") {
			frm.add_custom_button(__("Naikkan ke TM"), function() {
				show_naik_tm_dialog(frm);
			});
		}

		if (frm.doc.workflow_state === "TM") {
			let btn = frm.add_custom_button(__("Kembalikan ke TBM"), function() {
				frappe.confirm(
					__(
						"Blok-Blok yang dinaikkan ke TM bersamaan dengan Blok ini (dalam Journal Entry yang sama) akan dikembalikan ke TBM, dan Journal Entry terkait akan dibatalkan. Lanjutkan?"
					),
					function() {
						frappe.call({
							method: "sth.plantation.doctype.blok.blok.kembalikan_ke_tbm",
							args: { blok_name: frm.doc.name },
							freeze: true,
							freeze_message: __("Memproses..."),
							callback: function(r) {
								if (r.message) {
									frappe.msgprint({
										title: __("Berhasil"),
										indicator: "orange",
										message: __(
											"{0} Blok berhasil dikembalikan ke TBM.<br>Journal Entry <a href='/app/journal-entry/{1}'>{1}</a> telah dibatalkan.",
											[r.message.blok_diproses, r.message.journal_entry]
										)
									});
									frm.reload_doc();
								}
							}
						});
					}
				);
			});
			$(btn).addClass("btn-danger");
		}
	},

	unit(frm) {
		set_account_tbm_query(frm);
	}
});

function show_naik_tm_dialog(frm) {
	frappe.call({
		method: "sth.plantation.doctype.blok.blok.get_tbm_bloks_for_selection",
		args: { blok_name: frm.doc.name },
		callback: function(r) {
			if (!r.message) return;
			let data = r.message;

			let dialog = new frappe.ui.Dialog({
				title: __("Pilih Blok yang akan Dinaikkan ke TM"),
				fields: [
					{
						fieldname: "info",
						fieldtype: "HTML",
						options: `<p>Tahun Tanam <b>${data.tahun_tanam}</b> - Unit <b>${data.unit}</b></p>`
					},
					{
						fieldname: "bloks",
						fieldtype: "MultiCheck",
						label: __("Blok TBM"),
						options: data.bloks.map((b) => ({
							label: `${b.blok} (${b.luas_areal} ha)`,
							value: b.name,
							checked: b.name === frm.doc.name
						})),
						columns: 2
					}
				],
				primary_action_label: __("Preview"),
				primary_action: function() {
					let selected = dialog.get_values().bloks || [];
					if (!selected.length) {
						frappe.msgprint(__("Pilih minimal satu Blok."));
						return;
					}
					dialog.hide();
					show_naik_tm_preview(frm, selected);
				}
			});

			dialog.show();
		}
	});
}

function show_naik_tm_preview(frm, selected_bloks) {
	frappe.call({
		method: "sth.plantation.doctype.blok.blok.preview_naikkan_ke_tm",
		args: {
			blok_name: frm.doc.name,
			selected_bloks: selected_bloks
		},
		callback: function(r) {
			if (!r.message) return;
			let p = r.message;
			let fmt_total = frappe.format(p.total, { fieldtype: "Currency" });
			let fmt_biaya = frappe.format(p.total_biaya, { fieldtype: "Currency" });
			let msg = `
				<table class="table table-bordered table-condensed" style="margin-top:8px">
					<tr><td><b>Tahun Tanam</b></td><td>${p.tahun_tanam}</td></tr>
					<tr><td><b>Unit</b></td><td>${p.unit}</td></tr>
					<tr><td><b>Jumlah Blok TBM (Tahun Tanam ini)</b></td><td>${p.jumlah_blok_cohort} blok</td></tr>
					<tr><td><b>Total Biaya (Tahun Tanam ini)</b></td><td>${fmt_biaya}</td></tr>
					<tr><td><b>Total Luas Areal (Tahun Tanam ini)</b></td><td>${p.total_hektar} ha</td></tr>
					<tr><td><b>Blok Dipilih</b></td><td>${p.jumlah_blok} blok (${p.luas_dipilih} ha)</td></tr>
					<tr><td><b>Total Nilai JE</b></td><td>${fmt_total}</td></tr>
					<tr><td><b>Debit</b></td><td>${p.debit_account}</td></tr>
					<tr><td><b>Kredit</b></td><td>${p.credit_account}</td></tr>
				</table>
				<p>${p.jumlah_blok} Blok yang dipilih akan dinaikkan ke <b>TM</b> dan 1 Journal Entry akan dibuat. Lanjutkan?</p>
			`;
			frappe.confirm(msg, function() {
				frappe.call({
					method: "sth.plantation.doctype.blok.blok.naikkan_ke_tm",
					args: {
						blok_name: frm.doc.name,
						selected_bloks: selected_bloks
					},
					freeze: true,
					freeze_message: __("Memproses Naik TM..."),
					callback: function(r) {
						if (r.message) {
							frappe.msgprint({
								title: __("Berhasil"),
								indicator: "green",
								message: __(
									"{0} Blok berhasil dinaikkan ke TM.<br>Journal Entry: <a href='/app/journal-entry/{1}'>{1}</a>",
									[r.message.blok_diproses, r.message.journal_entry]
								)
							});
							frm.reload_doc();
						}
					}
				});
			});
		}
	});
}

function set_account_tbm_query(frm) {
	if (!frm.doc.unit) {
		frm.set_query("account_tbm", function() {
			return {
				filters: [
					["is_group", "=", 0],
					["account_number", "like", "126%"]
				]
			};
		});
		return;
	}

	frappe.db.get_value("Unit", frm.doc.unit, "company", function(r) {
		let company = r && r.company;
		frm.set_query("account_tbm", function() {
			let filters = [
				["is_group", "=", 0],
				["account_number", "like", "126%"]
			];
			if (company) {
				filters.push(["company", "=", company]);
			}
			return { filters };
		});
	});
}
