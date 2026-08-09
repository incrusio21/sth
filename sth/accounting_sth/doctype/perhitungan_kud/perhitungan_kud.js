// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Perhitungan KUD", {
	setup(frm) {
		// Dua argumen, bukan tiga. Bentuk set_query(field, parentfield, fn) itu
		// untuk grid child table dan mencari `.grid` — Table MultiSelect tidak
		// punya itu, jadi bentuk tiga argumen melempar error saat form dibuka.
		frm.set_query("unit", () => ({
			filters: { company: frm.doc.company, plasma: 1 },
		}));
	},

	refresh(frm) {
		if (frm.doc.docstatus !== 0) return;

		frm.add_custom_button(__("Tarik Produksi"), () => tarik_produksi(frm)).addClass(
			"btn-primary"
		);
	},

	company(frm) {
		frm.clear_table("unit");
		frm.refresh_field("unit");
		isi_unit_plasma(frm);
	},
});

function isi_unit_plasma(frm) {
	if (!frm.doc.company) return;

	frappe.call({
		method: "sth.accounting_sth.doctype.perhitungan_kud.perhitungan_kud.get_unit_plasma",
		args: { company: frm.doc.company },
		callback(r) {
			if (!r.message || !r.message.length) {
				frappe.msgprint(__("{0} belum punya unit yang ditandai plasma.", [frm.doc.company]));
				return;
			}

			r.message.forEach((unit) => frm.add_child("unit", { unit: unit }));
			frm.refresh_field("unit");

			frappe.show_alert({
				message: __("{0} unit plasma dimuat. Kurangi kalau tidak semuanya milik mitra ini.", [
					r.message.length,
				]),
				indicator: "blue",
			});
		},
	});
}

function tarik_produksi(frm) {
	if ((frm.doc.detail || []).length) {
		frappe.confirm(__("Detail produksi yang sekarang akan diganti. Lanjutkan?"), () =>
			jalankan(frm)
		);
		return;
	}

	jalankan(frm);
}

function jalankan(frm) {
	frm.call({
		doc: frm.doc,
		method: "tarik_produksi",
		freeze: true,
		freeze_message: __("Menarik produksi dari timbangan..."),
		callback(r) {
			frm.refresh();

			if (!r.message) return;

			if (!r.message.jumlah_baris) {
				frappe.msgprint(
					__("Tidak ada timbangan tersubmit di rentang tanggal ini untuk unit yang dipilih.")
				);
				return;
			}

			frappe.show_alert({
				message: __("{0} baris ditarik. {1}", [
					r.message.jumlah_baris,
					r.message.status_harga,
				]),
				indicator: "green",
			});
		},
	});
}
