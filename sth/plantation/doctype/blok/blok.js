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
				frappe.call({
					method: "sth.plantation.doctype.blok.blok.preview_naikkan_ke_tm",
					args: { blok_name: frm.doc.name },
					callback: function(r) {
						if (!r.message) return;
						let p = r.message;
						let fmt_total = frappe.format(p.total, { fieldtype: "Currency" });
						let msg = `
							<table class="table table-bordered table-condensed" style="margin-top:8px">
								<tr><td><b>Tahun Tanam</b></td><td>${p.tahun_tanam}</td></tr>
								<tr><td><b>Unit</b></td><td>${p.unit}</td></tr>
								<tr><td><b>Jumlah Blok TBM</b></td><td>${p.jumlah_blok} blok</td></tr>
								<tr><td><b>Total Nilai JE</b></td><td>${fmt_total}</td></tr>
								<tr><td><b>Debit</b></td><td>${p.debit_account}</td></tr>
								<tr><td><b>Kredit</b></td><td>${p.credit_account}</td></tr>
							</table>
							<p>Semua ${p.jumlah_blok} Blok di atas akan dinaikkan ke <b>TM</b> dan 1 Journal Entry akan dibuat. Lanjutkan?</p>
						`;
						frappe.confirm(msg, function() {
							frappe.call({
								method: "sth.plantation.doctype.blok.blok.naikkan_ke_tm",
								args: { blok_name: frm.doc.name },
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
			});
		}

		if (frm.doc.workflow_state === "TM") {
			let btn = frm.add_custom_button(__("Kembalikan ke TBM"), function() {
				frappe.confirm(
					__(
						"Semua Blok dengan tahun tanam <b>{0}</b> dan unit <b>{1}</b> yang berstatus TM akan dikembalikan ke TBM, dan Journal Entry terkait akan dibatalkan. Lanjutkan?",
						[frm.doc.tahun_tanam, frm.doc.unit]
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
