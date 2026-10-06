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

		[...FIELD_AKUN, "cost_center"].forEach((fieldname) => {
			frm.set_query(fieldname, () => ({
				filters: { company: frm.doc.company, is_group: 0 },
			}));
		});
	},

	refresh(frm) {
		tampilkan_belum_bb(frm);

		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Lihat Jurnal"), () => lihat_jurnal(frm), __("Akuntansi"));
			tombol_turunan(frm);
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

		// Akun company lama dikosongkan, bukan dibiarkan: server cuma mengisi
		// yang kosong dari setelan, jadi sisa company lama tidak akan tertimpa.
		[...FIELD_AKUN, "cost_center"].forEach((fieldname) => frm.set_value(fieldname, null));
	},
});

const FIELD_AKUN = [
	"akun_pembelian_tbs",
	"akun_management_fee",
	"akun_pph22",
	"akun_piutang_plasma",
	"akun_hutang_plasma_antara",
	"akun_lain_lain",
	"akun_hutang_mitra",
];

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
			__("Detail produksi dan biaya BKM & BAPP yang sekarang akan diganti. Lanjutkan?"),
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
		freeze_message: __("Menarik produksi dari timbangan dan biaya dari BKM & BAPP..."),
		callback(r) {
			frm.refresh();

			if (!r.message) return;

			const biaya = frappe.format(r.message.biaya_perawatan, { fieldtype: "Currency" });
			const biaya_bapp = frappe.format(r.message.biaya_bapp, { fieldtype: "Currency" });

			if (!r.message.jumlah_baris) {
				frappe.msgprint(
					__(
						"Tidak ada timbangan tersubmit di rentang tanggal ini untuk unit yang dipilih. Biaya dari {0} BKM ({1}) dan {2} BAPP ({3}) tetap ditarik.",
						[r.message.jumlah_bkm, biaya, r.message.jumlah_bapp, biaya_bapp]
					)
				);
				return;
			}

			frappe.show_alert({
				message: __("{0} baris ditarik, {1} BKM senilai {2}, {3} BAPP senilai {4}. {5} Jurnal: {6}.", [
					r.message.jumlah_baris,
					r.message.jumlah_bkm,
					biaya,
					r.message.jumlah_bapp,
					biaya_bapp,
					r.message.status_harga,
					r.message.status_jurnal,
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
	// Sakelarnya satu centang di STH Accounting Settings. Selama mati, seluruh
	// grup tombolnya hilang — yang "Buat" maupun yang "Lihat". Dokumen turunan
	// yang sudah terlanjur dibuat tetap ada dan masih bisa dibuka lewat daftarnya
	// sendiri, cuma pintasnya dari sini yang ikut ditutup.
	if (!(frm.doc.__onload && frm.doc.__onload.turunan_aktif)) return;

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

// Biaya yang ditagih ke mitra tapi belum punya GL. Sebagian tetap dijurnal di
// muka (akunnya di bawah Kepala Akun Biaya), sisanya tidak — kolom Dijurnal.
// Barisnya tersimpan per dokumen di child table tersembunyi `belum_bb`; di sini
// dikelompokkan per akun, dan klik satu akun membuka daftar dokumennya.
function tampilkan_belum_bb(frm) {
	const wrapper = frm.get_field("belum_bb_html").$wrapper;
	const rows = frm.doc.belum_bb || [];
	const esc = frappe.utils.escape_html;
	const uang = (v) => format_currency(v, frm.doc.currency);

	if (!rows.length) {
		wrapper.html(
			`<p class="text-muted small">${__("Semua biaya sudah masuk buku besar, atau produksi belum ditarik.")}</p>`
		);
		return;
	}

	const grup = kelompokkan_belum_bb(rows);
	const total = grup.reduce((n, g) => n + g.belum, 0);
	const total_dijurnal = grup.reduce((n, g) => n + (g.dijurnal ? g.belum : 0), 0);

	const baris = grup
		.map(
			(g, i) => `
			<tr class="belum-bb-grup" data-idx="${i}" style="cursor: pointer">
				<td>${esc(g.label)}</td>
				<td>${g.dijurnal ? __("Ya") : __("Tidak")}</td>
				<td class="text-right">${g.dokumen.size || "-"}</td>
				<td class="text-right">${uang(g.belum)}</td>
			</tr>`
		)
		.join("");

	wrapper.html(`
		<p class="text-muted small">${esc(frm.doc.status_jurnal || "")}</p>
		<table class="table table-bordered table-hover table-sm">
			<thead>
				<tr>
					<th>${__("Akun")}</th>
					<th style="width: 10%">${__("Dijurnal")}</th>
					<th class="text-right" style="width: 12%">${__("Dokumen")}</th>
					<th class="text-right" style="width: 25%">${__("Belum di Buku Besar")}</th>
				</tr>
			</thead>
			<tbody>${baris}</tbody>
			<tfoot>
				<tr>
					<th colspan="3">${__("Ikut dijurnal")}</th>
					<th class="text-right">${uang(total_dijurnal)}</th>
				</tr>
				<tr>
					<th colspan="3">${__("Tidak dijurnal")}</th>
					<th class="text-right">${uang(total - total_dijurnal)}</th>
				</tr>
				<tr>
					<th colspan="3">${__("Total")}</th>
					<th class="text-right">${uang(total)}</th>
				</tr>
			</tfoot>
		</table>
		<p class="text-muted small">${__("Klik satu akun untuk melihat dokumennya.")}</p>
	`);

	wrapper.find(".belum-bb-grup").on("click", function () {
		detail_belum_bb(frm, grup[$(this).data("idx")]);
	});
}

function kelompokkan_belum_bb(rows) {
	const peta = new Map();

	rows.forEach((row) => {
		const label = row.akun || row.keterangan || __("Tanpa akun");
		// Satu akun bisa punya bagian yang dijurnal dan yang tidak (misalnya
		// BKM Perawatan tanpa cost center), jadi keduanya grup terpisah.
		const kunci = `${label}|${row.dijurnal ? 1 : 0}`;
		if (!peta.has(kunci)) {
			peta.set(kunci, { label, dijurnal: !!row.dijurnal, belum: 0, dokumen: new Set(), rows: [] });
		}

		const g = peta.get(kunci);
		g.belum += flt(row.belum);
		g.rows.push(row);
		if (row.voucher_no) g.dokumen.add(row.voucher_no);
	});

	return [...peta.values()].sort((a, b) => b.belum - a.belum);
}

function detail_belum_bb(frm, grup) {
	const esc = frappe.utils.escape_html;
	const uang = (v) => format_currency(v, frm.doc.currency);

	const baris = grup.rows
		.map((row) => {
			const dokumen = row.voucher_no
				? `<a href="${frappe.utils.get_form_link(row.voucher_type, row.voucher_no)}" target="_blank">${esc(row.voucher_no)}</a>
				   <div class="text-muted small">${esc(__(row.voucher_type))}</div>`
				: esc(row.keterangan || "");

			return `
				<tr>
					<td>${dokumen}</td>
					<td>${row.posting_date ? frappe.datetime.str_to_user(row.posting_date) : ""}</td>
					<td>${esc(row.status_dokumen || "")}</td>
				<td>${esc(row.cost_center || "")}</td>
					<td class="text-right">${row.voucher_no ? uang(row.nilai_dokumen) : ""}</td>
					<td class="text-right">${row.voucher_no ? uang(row.sudah_buku_besar) : ""}</td>
					<td class="text-right">${uang(row.belum)}</td>
				</tr>`;
		})
		.join("");

	const dialog = new frappe.ui.Dialog({
		title: `${grup.label} — ${grup.dijurnal ? __("ikut dijurnal") : __("tidak dijurnal")}`,
		size: "extra-large",
		fields: [{ fieldtype: "HTML", fieldname: "isi" }],
	});

	dialog.fields_dict.isi.$wrapper.html(`
		<div style="max-height: 60vh; overflow: auto">
			<table class="table table-bordered table-sm">
				<thead>
					<tr>
						<th>${__("Dokumen")}</th>
						<th>${__("Tanggal")}</th>
						<th>${__("Status")}</th>
						<th>${__("Cost Center")}</th>
						<th class="text-right">${__("Nilai Dokumen")}</th>
						<th class="text-right">${__("Sudah di Buku Besar")}</th>
						<th class="text-right">${__("Belum (bagian akun ini)")}</th>
					</tr>
				</thead>
				<tbody>${baris}</tbody>
				<tfoot>
					<tr>
						<th colspan="6">${__("Total")}</th>
						<th class="text-right">${uang(grup.belum)}</th>
					</tr>
				</tfoot>
			</table>
		</div>
	`);

	dialog.show();
}
