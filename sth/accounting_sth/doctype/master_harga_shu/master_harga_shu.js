// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.provide("sth.shu");

// Bulan di matriks ditulis dengan angka romawi, sejajar dengan BULAN_ROMAWI
// di master_harga_shu.py
const BULAN_ROMAWI = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"];

function bulan_romawi(bulan_no) {
	return BULAN_ROMAWI[cint(bulan_no)] || bulan_no;
}

frappe.ui.form.on("Master Harga SHU", {
	refresh(frm) {
		frm.trigger("muat_matriks");
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
			method: "sth.accounting_sth.doctype.master_harga_shu.master_harga_shu.get_masa_setahun",
			args: { company: frm.doc.company, tahun: frm.doc.tahun },
			callback(r) {
				const masa = r.message || [];

				frappe.call({
					method:
						"sth.accounting_sth.doctype.master_harga_shu.master_harga_shu.get_tahun_tanam_per_bulan",
					args: { company: frm.doc.company, tahun: frm.doc.tahun },
					callback(r2) {
						frm.matriks = new sth.shu.MatriksHarga(wrapper, frm, masa, r2.message || {});
					},
				});
			},
		});
	},
});

sth.shu.MatriksHarga = class MatriksHarga {
	constructor(wrapper, frm, masa, tt_per_bulan) {
		this.wrapper = wrapper;
		this.frm = frm;
		this.masa = masa;
		this.tt_per_bulan = tt_per_bulan || {};
		this.render();
	}

	tahun_tanam() {
		return (this.frm.doc.tahun_tanam || [])
			.map((r) => cint(r.tahun_tanam))
			.filter(Boolean)
			.sort((a, b) => b - a);
	}

	// Kolom sebuah bulan: tahun tanam yang benar-benar ada buahnya di bulan itu,
	// ditambah yang sudah terlanjur punya harga supaya angka lama tidak hilang
	// dari layar begitu tiketnya berubah.
	tahun_tanam_bulan(bulan_no) {
		const dari_timbangan = (this.tt_per_bulan[bulan_no] || []).map(cint);
		const berharga = (this.frm.doc.harga || [])
			.filter((r) => cint(r.bulan_no) === cint(bulan_no))
			.map((r) => cint(r.tahun_tanam));

		return Array.from(new Set([...dari_timbangan, ...berharga]))
			.filter(Boolean)
			.sort((a, b) => b - a);
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
	nilai(bulan_no, masa_no, tt) {
		const baris = (this.frm.doc.harga || []).find(
			(r) =>
				cint(r.bulan_no) === bulan_no && cint(r.masa_no) === masa_no && cint(r.tahun_tanam) === tt
		);
		return baris ? baris.harga : undefined;
	}

	tulis(bulan_no, masa_no, tt, nilai) {
		const harga = this.frm.doc.harga || [];
		const idx = harga.findIndex(
			(r) =>
				cint(r.bulan_no) === bulan_no && cint(r.masa_no) === masa_no && cint(r.tahun_tanam) === tt
		);

		if (nilai === undefined) {
			if (idx >= 0) this.frm.get_field("harga").grid.grid_rows[idx].remove();
			return;
		}

		if (idx >= 0) {
			harga[idx].harga = nilai;
		} else {
			const baru = this.frm.add_child("harga");
			baru.bulan_no = bulan_no;
			baru.masa_no = masa_no;
			baru.tahun_tanam = tt;
			baru.harga = nilai;
		}

		this.frm.dirty();
	}

	render() {
		if (!this.masa.length) {
			this.wrapper.html(
				`<p class="text-muted">${__("Belum ada Masa SHU yang disubmit untuk tahun ini.")}</p>`
			);
			return;
		}

		if (!this.tahun_tanam().length) {
			this.wrapper.html(
				`<p class="text-muted">${__("Belum ada tahun tanam di tiket timbangan tahun ini.")}</p>`
			);
			return;
		}

		const terkunci = this.bulan_terkunci();
		const per_bulan = {};
		this.masa.forEach((m) => {
			(per_bulan[m.bulan_no] = per_bulan[m.bulan_no] || {
				bulan: bulan_romawi(m.bulan_no),
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
				const tts = this.tahun_tanam_bulan(bulan_no);

				html += `<div style="margin-bottom:14px">
					<div style="background:var(--control-bg);font-weight:500;padding:6px 8px;border:1px solid var(--border-color);border-bottom:0">
						${bl.bulan}
						<span class="text-muted small" style="margin-left:8px">${bl.baris.length} ${__("masa")}</span>
						${kunci ? `<span class="indicator-pill green" style="margin-left:8px">${__("Ditetapkan")}</span>` : ""}
						<button class="btn btn-xs btn-default shu-toggle" data-bulan="${bulan_no}"
							style="float:right">${kunci ? __("Buka") : __("Tetapkan")}</button>
					</div>`;

				if (!tts.length) {
					html += `<div class="text-muted small"
						style="padding:8px;border:1px solid var(--border-color)">
						${__("Tidak ada buah masuk di bulan ini.")}</div></div>`;
					return;
				}

				html += `<div style="overflow-x:auto">
					<table class="table table-bordered" style="table-layout:fixed;margin-bottom:0">
					<thead><tr><th style="width:190px">${__("Masa")}</th>`;

				tts.forEach((tt) => {
					html += `<th style="width:120px;text-align:center">${tt}
						<div class="text-muted small">${cint(this.frm.doc.tahun) - tt}TH</div></th>`;
				});
				html += "</tr></thead><tbody>";

				bl.baris.forEach((m) => {
					html += `<tr><td><b>${__("Masa")} ${m.masa_no}</b>
						<span class="text-muted small"> ${frappe.datetime.str_to_user(m.tanggal_mulai)}
						&ndash; ${frappe.datetime.str_to_user(m.tanggal_selesai)}</span></td>`;

					tts.forEach((tt) => {
						const v = this.nilai(bulan_no, m.masa_no, tt);
						const ada = v !== undefined;
						html += `<td style="padding:0${ada ? "" : ";background:var(--bg-yellow)"}">
							<input class="shu-sel form-control" style="border:0;text-align:right;background:transparent"
								data-bulan="${bulan_no}" data-masa="${m.masa_no}" data-tt="${tt}"
								data-kolom="${tts.length}"
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

			$el.on("focus", function () {
				const v = me.nilai(cint($el.data("bulan")), cint($el.data("masa")), cint($el.data("tt")));
				$el.val(v === undefined ? "" : v);
			});

			$el.on("blur", function () {
				const angka = me.parse($el.val());
				me.tulis(
					cint($el.data("bulan")),
					cint($el.data("masa")),
					cint($el.data("tt")),
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
					this.tulis(cint($t.data("bulan")), cint($t.data("masa")), cint($t.data("tt")), angka);
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
				method: "sth.accounting_sth.doctype.master_harga_shu.master_harga_shu.tetapkan_bulan",
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
					method: "sth.accounting_sth.doctype.master_harga_shu.master_harga_shu.buka_bulan",
					args: { nama: this.frm.doc.name, bulan_no: bulan_no, alasan: nilai.alasan },
					callback: () => this.frm.reload_doc(),
				});
			},
			__("Buka Kembali Bulan Ini"),
			__("Buka")
		);
	}
};
