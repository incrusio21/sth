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
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Lihat Jurnal"), () => lihat_jurnal(frm), __("Akuntansi"));
			// tombol_turunan(frm);
			return;
		}

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
		frappe.confirm(
			__("Detail produksi dan biaya BKM yang sekarang akan diganti. Lanjutkan?"),
			() => jalankan(frm)
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
		freeze_message: __("Menarik produksi dari timbangan dan biaya dari BKM..."),
		callback(r) {
			frm.refresh();

			if (!r.message) return;

			const biaya = frappe.format(r.message.biaya_perawatan, { fieldtype: "Currency" });

			if (!r.message.jumlah_baris) {
				frappe.msgprint(
					__(
						"Tidak ada timbangan tersubmit di rentang tanggal ini untuk unit yang dipilih. Biaya dari {0} BKM tetap ditarik: {1}.",
						[r.message.jumlah_bkm, biaya]
					)
				);
				return;
			}

			frappe.show_alert({
				message: __("{0} baris ditarik, {1} BKM senilai {2}. {3}", [
					r.message.jumlah_baris,
					r.message.jumlah_bkm,
					biaya,
					r.message.status_harga,
				]),
				indicator: "green",
			});
		},
	});
}

function lihat_jurnal(frm) {
	// Jurnalnya berupa GL Entry langsung, tanpa Journal Entry perantara, jadi
	// yang bisa dibuka cuma General Ledger-nya.
	frappe.route_options = {
		company: frm.doc.company,
		from_date: frm.doc.tanggal_mulai,
		to_date: frm.doc.tanggal_selesai,
		voucher_no: frm.doc.name,
		group_by: "",
	};
	frappe.set_route("query-report", "General Ledger");
}

// Dua baris jurnal KUD diselesaikan dokumen lain: Management Fee oleh Nota
// Piutang, Pembayaran ke Mitra oleh Purchase Invoice. Tombolnya di sini, bukan
// di dokumen tujuan, supaya angkanya selalu ikut sumbernya.
const TURUNAN = [
	{
		doctype: "Nota Piutang",
		nilai: "management_fee",
		method: "sth.accounting_sth.doctype.perhitungan_kud.perhitungan_kud.buat_nota_piutang",
	},
	{
		doctype: "Purchase Invoice",
		nilai: "pembayaran_ke_mitra",
		method: "sth.accounting_sth.doctype.perhitungan_kud.perhitungan_kud.buat_purchase_invoice",
	},
];

function tombol_turunan(frm) {
	const sudah_ada = (frm.doc.__onload && frm.doc.__onload.turunan) || {};

	TURUNAN.forEach((t) => {
		const ada = sudah_ada[t.doctype];

		if (ada) {
			frm.add_custom_button(
				__("Lihat {0}", [__(t.doctype)]),
				() => frappe.set_route("Form", t.doctype, ada),
				__("Akuntansi")
			);
			return;
		}

		if (!frm.doc[t.nilai]) return;

		frm.add_custom_button(
			__(t.doctype),
			() => frappe.model.open_mapped_doc({ method: t.method, frm: frm }),
			__("Buat")
		);
	});
}
