// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Masa SHU", {
	refresh(frm) {
		if (frm.doc.docstatus !== 0) return;

		frm.add_custom_button(__("Bagi Rata Jadi N Masa"), () => minta_jumlah_masa(frm));
	},
});

frappe.ui.form.on("Masa SHU Detail", {
	detail_add(frm) {
		nomori_ulang(frm);
	},
	detail_remove(frm) {
		nomori_ulang(frm);
	},
	detail_move(frm) {
		nomori_ulang(frm);
	},
});

function minta_jumlah_masa(frm) {
	if (!frm.doc.tahun || !frm.doc.bulan) {
		frappe.msgprint(__("Isi Tahun dan Bulan dulu."));
		return;
	}

	if ((frm.doc.detail || []).length) {
		frappe.confirm(__("Pembagian masa yang sekarang akan diganti. Lanjutkan?"), () => tanya(frm));
		return;
	}

	tanya(frm);
}

function tanya(frm) {
	frappe.prompt(
		{
			fieldname: "jumlah",
			label: __("Jumlah Masa"),
			fieldtype: "Int",
			reqd: 1,
			default: 4,
			description: __("Cuma usulan awal — tanggalnya bisa digeser setelah dibuat."),
		},
		(nilai) => isi_masa(frm, nilai.jumlah),
		__("Bagi Rata Jadi N Masa"),
		__("Buat")
	);
}

function isi_masa(frm, jumlah) {
	frappe.call({
		method: "sth.plantation.doctype.masa_shu.masa_shu.usulan_bagi_rata",
		args: { tahun: frm.doc.tahun, bulan: frm.doc.bulan, jumlah: jumlah },
		callback(r) {
			if (!r.message) return;

			frm.clear_table("detail");
			r.message.forEach((row) => {
				const baris = frm.add_child("detail");
				baris.masa_no = row.masa_no;
				baris.tanggal_mulai = row.tanggal_mulai;
				baris.tanggal_selesai = row.tanggal_selesai;
				baris.jumlah_hari = row.jumlah_hari;
			});
			frm.refresh_field("detail");

			frappe.show_alert({
				message: __("{0} masa dibuat. Geser tanggalnya sesuai keputusan bulan ini.", [jumlah]),
				indicator: "green",
			});
		},
	});
}

function nomori_ulang(frm) {
	(frm.doc.detail || []).forEach((baris, i) => {
		baris.masa_no = i + 1;
	});
	frm.refresh_field("detail");
}
