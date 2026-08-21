// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Asset Scrap Request", {
	setup(frm) {
		frm.set_query("asset", function () {
			return {
				filters: {
					docstatus: 1,
					status: ["not in", ["Draft", "Cancelled", "Sold", "Scrapped", "Capitalized", "Decapitalized"]]
				}
			};
		});
	},

	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;

		frm.add_custom_button(__("Asset"), function () {
			frappe.set_route("Form", "Asset", frm.doc.asset);
		}, __("View"));

		// Scrap penuh maupun sebagian sama-sama menjurnal lewat Journal Entry
		// sendiri, jadi jejaknya cukup dibuka dari jurnalnya
		if (frm.doc.journal_entry_for_scrap) {
			frm.add_custom_button(__("Journal Entry"), function () {
				frappe.set_route("Form", "Journal Entry", frm.doc.journal_entry_for_scrap);
			}, __("View"));
		}
	}
});
