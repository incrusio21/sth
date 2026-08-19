// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

// Uang muka Purchase Order di Purchase Invoice. Perhitungan sebenarnya ada di
// sth/buying_sth/custom/uang_muka_po.py — di sini cuma tombol penarik dan
// tampilan totalnya, supaya angkanya tidak menunggu save untuk terlihat.

function hitung_total_uang_muka(frm) {
	const total = (frm.doc.uang_muka_po || []).reduce((jumlah, row) => jumlah + flt(row.dipakai), 0);

	frm.set_value("total_uang_muka", total);
	frm.set_value(
		"grand_total_setelah_dp",
		flt(frm.doc.rounded_total || frm.doc.grand_total) - flt(frm.doc.total_advance) - total
	);
}

frappe.ui.form.on("Purchase Invoice", {
	refresh(frm) {
		if (frm.doc.docstatus !== 0 || frm.doc.is_return) {
			return;
		}

		if (!(frm.doc.items || []).some((row) => row.purchase_order)) {
			return;
		}

		frm.add_custom_button(__("Ambil Uang Muka PO"), () => {
			frm.call({
				method: "set_uang_muka_po",
				doc: frm.doc,
				freeze: true,
				freeze_message: __("Mengambil uang muka Purchase Order..."),
				callback() {
					frm.refresh_field("uang_muka_po");
					frm.refresh_field("total_uang_muka");
					frm.refresh_field("grand_total_setelah_dp");

					if (!(frm.doc.uang_muka_po || []).length) {
						frappe.msgprint({
							title: __("Uang Muka PO"),
							message: __(
								"Tidak ada uang muka Purchase Order yang masih bersisa untuk invoice ini."
							),
							indicator: "orange",
						});
					}
				},
			});
		});
	},

	uang_muka_po_remove(frm) {
		hitung_total_uang_muka(frm);
	},
});

frappe.ui.form.on("Uang Muka Purchase Invoice", {
	dipakai(frm, cdt, cdn) {
		const row = locals[cdt][cdn];

		if (flt(row.dipakai) > flt(row.sisa)) {
			frappe.msgprint({
				title: __("Uang Muka PO"),
				message: __("Uang muka yang dipakai tidak boleh melebihi sisanya ({0}).", [
					format_currency(row.sisa, frm.doc.currency),
				]),
				indicator: "red",
			});
			frappe.model.set_value(cdt, cdn, "dipakai", row.sisa);
			return;
		}

		if (flt(row.dipakai) < 0) {
			frappe.model.set_value(cdt, cdn, "dipakai", 0);
			return;
		}

		hitung_total_uang_muka(frm);
	},
});
