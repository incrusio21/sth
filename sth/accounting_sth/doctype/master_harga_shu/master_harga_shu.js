// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.provide("sth.shu");

const SHU_API = "sth.accounting_sth.doctype.master_harga_shu.master_harga_shu";

// Sejajar dengan BULAN_MAP di blok.py — indeks 1 sampai 12.
const BULAN = [
	"",
	"Januari",
	"Februari",
	"Maret",
	"April",
	"Mei",
	"Juni",
	"Juli",
	"Agustus",
	"September",
	"Oktober",
	"November",
	"Desember",
];

function nama_bulan(bulan_no) {
	return BULAN[cint(bulan_no)] || bulan_no;
}

function nomor_bulan(bulan) {
	const i = BULAN.indexOf(bulan);
	return i > 0 ? i : 0;
}

// Cerminan set_periode_masa() di sisi server: nomor masa diambil dari urutan
// baris dalam satu bulan. Dihitung ulang di sini supaya matriks tetap benar
// sebelum dokumennya disimpan.
function masa_dari_doc(frm) {
	const urutan = {};

	return (frm.doc.masa || [])
		.map((row) => {
			const bulan_no = nomor_bulan(row.bulan);
			if (!bulan_no) return null;

			urutan[bulan_no] = (urutan[bulan_no] || 0) + 1;

			return {
				bulan_no: bulan_no,
				bulan: row.bulan,
				masa_no: urutan[bulan_no],
				tanggal_mulai: row.tanggal_mulai,
				tanggal_selesai: row.tanggal_selesai,
			};
		})
		.filter(Boolean)
		.sort((a, b) => a.bulan_no - b.bulan_no || a.masa_no - b.masa_no);
}

frappe.ui.form.on("Master Harga SHU", {
	refresh(frm) {
		frm.trigger("muat_matriks");

		frm.add_custom_button(__("Bagi Rata Jadi N Masa"), () => bagi_rata(frm));
	},

	company(frm) {
		frm.trigger("muat_matriks");
	},

	tahun(frm) {
		frm.trigger("muat_matriks");
	},

	muat_matriks(frm) {
		const wrapper = frm.get_field("matriks").$wrapper;

		if (frm.is_new() || !frm.doc.company || !frm.doc.tahun) {
			wrapper.html(
				`<p class="text-muted">${__("Isi Company dan Tahun, lalu simpan sekali untuk memuat matriks.")}</p>`
			);
			return;
		}

		frappe.call({
			method: SHU_API + ".get_kelompok_umur",
			callback(r) {
				frm.matriks = new sth.shu.MatriksHarga(wrapper, frm, masa_dari_doc(frm), r.message || []);
			},
		});
	},
});

// Matriks membaca tabel Masa di dokumen ini, jadi tiap perubahan pembagian masa
// harus langsung tercermin di sana.
frappe.ui.form.on("Master Harga SHU Masa", {
	masa_add: (frm) => frm.trigger("muat_matriks"),
	masa_remove: (frm) => frm.trigger("muat_matriks"),
	masa_move: (frm) => frm.trigger("muat_matriks"),
	bulan: (frm) => frm.trigger("muat_matriks"),
	tanggal_mulai: (frm) => frm.trigger("muat_matriks"),
	tanggal_selesai: (frm) => frm.trigger("muat_matriks"),
});

function bagi_rata(frm) {
	if (!frm.doc.tahun) {
		frappe.msgprint(__("Isi Tahun dulu."));
		return;
	}

	frappe.prompt(
		[
			{
				fieldname: "bulan",
				label: __("Bulan"),
				fieldtype: "Select",
				options: BULAN.slice(1).join("\n"),
				reqd: 1,
			},
			{
				fieldname: "jumlah",
				label: __("Jumlah Masa"),
				fieldtype: "Int",
				reqd: 1,
				default: 4,
				description: __("Cuma usulan awal — tanggalnya bisa digeser setelah dibuat."),
			},
		],
		(nilai) => {
			const ada = (frm.doc.masa || []).some((r) => r.bulan === nilai.bulan);

			if (!ada) {
				isi_masa(frm, nilai.bulan, nilai.jumlah);
				return;
			}

			frappe.confirm(
				__("Pembagian masa {0} yang sekarang akan diganti. Lanjutkan?", [nilai.bulan]),
				() => isi_masa(frm, nilai.bulan, nilai.jumlah)
			);
		},
		__("Bagi Rata Jadi N Masa"),
		__("Buat")
	);
}

function isi_masa(frm, bulan, jumlah) {
	frappe.call({
		method: SHU_API + ".usulan_bagi_rata",
		args: { tahun: frm.doc.tahun, bulan: bulan, jumlah: jumlah },
		callback(r) {
			if (!r.message) return;

			// bulan lain tidak ikut terganggu — pembagiannya berdiri sendiri
			frm.doc.masa = (frm.doc.masa || []).filter((row) => row.bulan !== bulan);
			frm.doc.masa.forEach((row, i) => {
				row.idx = i + 1;
			});

			r.message.forEach((row) => {
				const baris = frm.add_child("masa");
				baris.bulan = bulan;
				baris.bulan_no = nomor_bulan(bulan);
				baris.masa_no = row.masa_no;
				baris.tanggal_mulai = row.tanggal_mulai;
				baris.tanggal_selesai = row.tanggal_selesai;
				baris.jumlah_hari = row.jumlah_hari;
			});

			frm.refresh_field("masa");
			frm.trigger("muat_matriks");

			frappe.show_alert({
				message: __("{0} masa dibuat untuk {1}. Geser tanggalnya sesuai keputusan bulan ini.", [
					jumlah,
					bulan,
				]),
				indicator: "green",
			});
		},
	});
}

sth.shu.MatriksHarga = class MatriksHarga {
	// Kolomnya kelompok umur yang paten, sama untuk semua bulan — daftarnya
	// datang dari server supaya cuma ada satu sumber.
	constructor(wrapper, frm, masa, kelompok) {
		this.wrapper = wrapper;
		this.frm = frm;
		this.masa = masa;
		this.kelompok = kelompok || [];
		this.render();
	}

	bulan_terkunci() {
		return new Set(
			(this.frm.doc.penetapan || [])
				.filter((r) => r.status === "Ditetapkan")
				.map((r) => cint(r.bulan_no))
		);
	}

	// Sel yang tidak punya baris di child table berarti belum ditetapkan.
	// Kosong dan nol sengaja dibedakan.
	nilai(bulan_no, masa_no, umur) {
		const baris = (this.frm.doc.harga || []).find(
			(r) =>
				cint(r.bulan_no) === bulan_no &&
				cint(r.masa_no) === masa_no &&
				r.kelompok_umur === umur
		);
		return baris ? baris.harga : undefined;
	}

	tulis(bulan_no, masa_no, umur, nilai) {
		const harga = this.frm.doc.harga || [];
		const idx = harga.findIndex(
			(r) =>
				cint(r.bulan_no) === bulan_no &&
				cint(r.masa_no) === masa_no &&
				r.kelompok_umur === umur
		);

		if (nilai === undefined) {
			if (idx >= 0) this.frm.get_field("harga").grid.grid_rows[idx].remove();
			return;
		}

		if (idx >= 0) {
			harga[idx].harga = nilai;
		} else {
			const kelompok = this.kelompok.find((k) => k.label === umur) || {};
			const baru = this.frm.add_child("harga");
			baru.bulan_no = bulan_no;
			baru.masa_no = masa_no;
			baru.kelompok_umur = umur;
			baru.umur_min = kelompok.umur_min;
			baru.umur_max = kelompok.umur_max;
			baru.harga = nilai;
		}

		this.frm.dirty();
	}

	render() {
		if (!this.masa.length) {
			this.wrapper.html(
				`<p class="text-muted">${__("Belum ada pembagian masa. Isi tabel Masa di atas dulu.")}</p>`
			);
			return;
		}

		if (!this.kelompok.length) {
			this.wrapper.html(
				`<p class="text-muted">${__("Daftar kelompok umur belum termuat.")}</p>`
			);
			return;
		}

		const terkunci = this.bulan_terkunci();
		const per_bulan = {};
		this.masa.forEach((m) => {
			(per_bulan[m.bulan_no] = per_bulan[m.bulan_no] || {
				bulan: nama_bulan(m.bulan_no),
				baris: [],
			}).baris.push(m);
		});

		// Tiap bulan dapat tabelnya sendiri karena kolom tahun tanamnya
		// mengikuti buah yang masuk di bulan itu, jadi bisa berbeda antar bulan.
		let html = `<div class="shu-matriks">`;

		Object.keys(per_bulan)
			.map(cint)
			.sort((a, b) => a - b)
			.forEach((bulan_no) => {
				const bl = per_bulan[bulan_no];
				const kunci = terkunci.has(bulan_no);
				const kolom = this.kelompok;

				html += `<div style="margin-bottom:14px">
					<div style="background:var(--control-bg);font-weight:500;padding:6px 8px;border:1px solid var(--border-color);border-bottom:0">
						${bl.bulan}
						<span class="text-muted small" style="margin-left:8px">${bl.baris.length} ${__("masa")}</span>
						${kunci ? `<span class="indicator-pill green" style="margin-left:8px">${__("Ditetapkan")}</span>` : ""}
						<button class="btn btn-xs btn-default shu-toggle" data-bulan="${bulan_no}"
							style="float:right">${kunci ? __("Buka") : __("Tetapkan")}</button>
					</div>`;

				html += `<div style="overflow-x:auto">
					<table class="table table-bordered" style="table-layout:fixed;margin-bottom:0">
					<thead><tr><th style="width:190px">${__("Masa")}</th>`;

				kolom.forEach((k) => {
					const keterangan =
						k.umur_max >= 999
							? __("{0} th ke atas", [k.umur_min])
							: __("umur {0} th", [k.label]);
					html += `<th style="width:120px;text-align:center">${k.label}
						<div class="text-muted small">${keterangan}</div></th>`;
				});
				html += "</tr></thead><tbody>";

				bl.baris.forEach((m) => {
					html += `<tr><td><b>${__("Masa")} ${m.masa_no}</b>
						<span class="text-muted small"> ${frappe.datetime.str_to_user(m.tanggal_mulai)}
						&ndash; ${frappe.datetime.str_to_user(m.tanggal_selesai)}</span></td>`;

					kolom.forEach((k) => {
						const v = this.nilai(bulan_no, m.masa_no, k.label);
						const ada = v !== undefined;
						html += `<td style="padding:0${ada ? "" : ";background:var(--bg-yellow)"}">
							<input class="shu-sel form-control" style="border:0;text-align:right;background:transparent"
								data-bulan="${bulan_no}" data-masa="${m.masa_no}" data-umur="${k.label}"
								data-kolom="${kolom.length}"
								${kunci ? "readonly" : ""}
								value="${ada ? format_number(v, null, 2) : ""}"></td>`;
					});
					html += "</tr>";
				});

				html += "</tbody></table></div></div>";
			});

		html += "</div>";
		this.wrapper.html(html);
		this.pasang();
	}

	pasang() {
		const me = this;
		const sel = this.wrapper.find(".shu-sel");

		this.wrapper.find(".shu-toggle").on("click", function () {
			me.ganti_penetapan(cint($(this).data("bulan")));
		});

		sel.each(function (i) {
			const $el = $(this);

			// label kelompok dibaca lewat attr(), bukan data(): jQuery mengubah
			// "3" jadi angka tapi "10 - 20" tetap string, dan perbandingannya
			// dengan isi child table jadi meleset
			$el.on("focus", function () {
				const v = me.nilai(cint($el.data("bulan")), cint($el.data("masa")), $el.attr("data-umur"));
				$el.val(v === undefined ? "" : v);
			});

			$el.on("blur", function () {
				const angka = me.parse($el.val());
				me.tulis(
					cint($el.data("bulan")),
					cint($el.data("masa")),
					$el.attr("data-umur"),
					angka
				);
				$el.val(angka === undefined ? "" : format_number(angka, null, 2));
				$el.closest("td").css("background", angka === undefined ? "var(--bg-yellow)" : "");
			});

			// jumlah kolom berbeda antar bulan, jadi lompatan atas-bawah
			// mengikuti lebar tabel bulan tempat sel ini berada
			const kolom = cint($el.data("kolom")) || 1;

			$el.on("keydown", function (e) {
				let j = null;
				if (e.key === "ArrowDown" || e.key === "Enter") j = i + kolom;
				else if (e.key === "ArrowUp") j = i - kolom;
				else if (e.key === "ArrowRight" && this.selectionStart === this.value.length) j = i + 1;
				else if (e.key === "ArrowLeft" && this.selectionStart === 0) j = i - 1;

				if (j !== null && sel[j]) {
					e.preventDefault();
					$el.blur();
					sel[j].focus();
					sel[j].select();
				}
			});

			$el.on("paste", function (e) {
				const teks = (e.originalEvent.clipboardData || window.clipboardData).getData("text");
				if (teks.indexOf("\t") < 0 && teks.indexOf("\n") < 0) return;
				e.preventDefault();
				me.tempel(sel, i, kolom, teks);
			});
		});
	}

	// Excel Indonesia menulis 3.406,67 — titik ribuan, koma desimal.
	parse(teks) {
		const bersih = (teks || "").trim().replace(/\./g, "").replace(/,/g, ".");
		if (!bersih) return undefined;
		const n = parseFloat(bersih);
		return isNaN(n) ? undefined : n;
	}

	tempel(sel, mulai, kolom, teks) {
		teks
			.replace(/\r/g, "")
			.split("\n")
			.forEach((baris, r) => {
				if (!baris.trim()) return;
				baris.split("\t").forEach((isi, c) => {
					const target = sel[mulai + r * kolom + c];
					if (!target || target.readOnly) return;

					const angka = this.parse(isi);
					if (angka === undefined) return;

					const $t = $(target);
					this.tulis(cint($t.data("bulan")), cint($t.data("masa")), $t.attr("data-umur"), angka);
					$t.val(format_number(angka, null, 2));
					$t.closest("td").css("background", "");
				});
			});
	}

	ganti_penetapan(bulan_no) {
		const terkunci = this.bulan_terkunci().has(bulan_no);

		if (this.frm.is_dirty()) {
			frappe.msgprint(__("Simpan dulu sebelum menetapkan atau membuka bulan."));
			return;
		}

		if (!terkunci) {
			frappe.call({
				method: SHU_API + ".tetapkan_bulan",
				args: { nama: this.frm.doc.name, bulan_no: bulan_no },
				callback: () => this.frm.reload_doc(),
			});
			return;
		}

		frappe.prompt(
			{
				fieldname: "alasan",
				label: __("Alasan Dibuka"),
				fieldtype: "Small Text",
				reqd: 1,
			},
			(nilai) => {
				frappe.call({
					method: SHU_API + ".buka_bulan",
					args: { nama: this.frm.doc.name, bulan_no: bulan_no, alasan: nilai.alasan },
					callback: () => this.frm.reload_doc(),
				});
			},
			__("Buka Kembali Bulan Ini"),
			__("Buka")
		);
	}
};
