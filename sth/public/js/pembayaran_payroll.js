// Pembayaran Payroll Entry per tipe: Gaji, PPh 21, Potongan, BPJS.
// Dipakai form Payment Entry (memilih tagihan yang dibayar) dan Payroll Entry
// (melihat tagihan, yang sudah dibayar, dan sisanya). Hitungannya di
// sth.hr_customize.pembayaran_payroll.

frappe.provide("sth.pembayaran_payroll");

$.extend(sth.pembayaran_payroll, {
	METHOD: "sth.hr_customize.pembayaran_payroll",

	kunci(d) {
		return [d.tipe, d.sub_tipe || "", d.account].join("\u0001");
	},

	uang(v) {
		return frappe.format(flt(v), { fieldtype: "Currency" });
	},

	tautan(doctype, name) {
		if (!name) return "—";
		const esc = frappe.utils.escape_html;
		return `<a href="/app/${frappe.router.slug(doctype)}/${encodeURIComponent(name)}" target="_blank">${esc(name)}</a>`;
	},

	label_tipe(d) {
		const esc = frappe.utils.escape_html;
		return esc(d.tipe) + (d.sub_tipe ? ` <span class="text-muted">— ${esc(d.sub_tipe)}</span>` : "");
	},

	ambil_tagihan(payroll_entry) {
		return frappe
			.call({
				method: `${this.METHOD}.get_tagihan_payroll`,
				args: { payroll_entry },
				freeze: true,
				freeze_message: __("Menghitung tagihan Payroll Entry..."),
			})
			.then((r) => r.message);
	},

	// Tabel tagihan. Dengan opsi pilih, tiap baris yang masih bersisa diberi
	// kotak centang, dan tiap tipe punya centang sendiri untuk memilih semua
	// sub tipenya sekaligus.
	tabel_tagihan(tagihan, { pilih = false, terpilih = new Set() } = {}) {
		const me = this;
		const esc = frappe.utils.escape_html;
		let tipe_sebelum = null;

		// Centang grup cuma untuk tipe yang masih punya baris bersisa.
		const tipe_bisa = new Set(tagihan.filter((d) => flt(d.sisa) > 0).map((d) => d.tipe));

		const baris = tagihan.map((d, i) => {
			let kepala = "";
			if (pilih && d.tipe !== tipe_sebelum) {
				kepala = `<tr style="background:var(--subtle-fg)">
					<td>${tipe_bisa.has(d.tipe) ? `<input type="checkbox" class="pilih-tipe" data-tipe="${esc(d.tipe)}">` : ""}</td>
					<td colspan="8"><b>${esc(d.tipe)}</b></td>
				</tr>`;
			}
			tipe_sebelum = d.tipe;

			let status = "";
			if (d.belum_diakrual) {
				status = `<span class="indicator-pill orange" title="${__("Akun ini tidak dikredit GL Payroll Entry (accrual cara lama)")}">${__("Belum diaccrual")}</span>`;
			} else if (flt(d.sisa) < 0) {
				status = `<span class="indicator-pill red">${__("Lebih bayar")}</span>`;
			} else if (flt(d.sisa) === 0) {
				status = `<span class="indicator-pill green">${__("Lunas")}</span>`;
			}

			const bisa = flt(d.sisa) > 0;
			const centang = pilih
				? `<td>${bisa ? `<input type="checkbox" class="pilih-baris" data-idx="${i}" data-tipe="${esc(d.tipe)}" ${terpilih.has(me.kunci(d)) ? "checked" : ""}>` : ""}</td>`
				: "";

			return `${kepala}<tr>
				${centang}
				<td>${me.label_tipe(d)}</td>
				<td>${esc(d.account || "")}${d.party ? `<br><small class="text-muted">${esc(d.party)}</small>` : ""}</td>
				<td style="text-align:right">${d.karyawan || ""}</td>
				<td style="text-align:right">${me.uang(d.tagihan)}</td>
				<td style="text-align:right">${me.uang(d.dibayar)}</td>
				<td style="text-align:right"><b>${me.uang(d.sisa)}</b></td>
				<td>${status}</td>
				<td><a class="lihat-dokumen" data-idx="${i}">${__("Dokumen")}</a></td>
			</tr>`;
		});

		const total = (f) => tagihan.reduce((s, d) => s + flt(d[f]), 0);

		return `<table class="table table-bordered table-condensed" style="margin-bottom:0">
			<thead style="background:var(--subtle-fg)"><tr>
				${pilih ? "<th></th>" : ""}
				<th>${__("Tipe")}</th>
				<th>${__("Akun")}</th>
				<th style="text-align:right">${__("Karyawan")}</th>
				<th style="text-align:right">${__("Tagihan")}</th>
				<th style="text-align:right">${__("Dibayar")}</th>
				<th style="text-align:right">${__("Sisa")}</th>
				<th></th><th></th>
			</tr></thead>
			<tbody>${baris.join("")}</tbody>
			<tfoot style="font-weight:bold"><tr>
				<td colspan="${pilih ? 4 : 3}" style="text-align:right">${__("Total")}</td>
				<td style="text-align:right">${me.uang(total("tagihan"))}</td>
				<td style="text-align:right">${me.uang(total("dibayar"))}</td>
				<td style="text-align:right">${me.uang(total("sisa"))}</td>
				<td></td><td></td>
			</tr></tfoot>
		</table>`;
	},

	tabel_pembayaran(pembayaran) {
		const me = this;
		if (!pembayaran.length) {
			return `<p class="text-muted">${__("Belum ada Payment Entry.")}</p>`;
		}
		const baris = pembayaran.map((d) => `<tr>
			<td>${me.tautan("Payment Entry", d.name)}${d.docstatus == 0 ? ` <span class="indicator-pill orange">${__("Draft")}</span>` : ""}</td>
			<td>${frappe.datetime.str_to_user(d.posting_date)}</td>
			<td>${frappe.utils.escape_html(d.paid_from || "")}</td>
			<td style="text-align:right">${me.uang(d.paid_amount)}</td>
		</tr>`);
		return `<table class="table table-bordered table-condensed">
			<thead style="background:var(--subtle-fg)"><tr>
				<th>${__("Payment Entry")}</th><th>${__("Tanggal")}</th><th>${__("Dari")}</th>
				<th style="text-align:right">${__("Jumlah")}</th>
			</tr></thead>
			<tbody>${baris.join("")}</tbody>
		</table>
		<p class="text-muted small">${__("Draft belum dihitung sebagai dibayar.")}</p>`;
	},

	// Dipanggil dari Payment Entry: pilih tagihan yang mau dibayar, lalu
	// tabel rincian_payroll diisi ulang dengan sisa tiap tagihan terpilih.
	pilih_tagihan(frm) {
		const me = this;
		if (!frm.doc.no_payroll_entry) {
			frappe.msgprint(__("Isi No Payroll Entry dulu."));
			return;
		}
		if (frm.__dialog_tagihan_payroll && frm.__dialog_tagihan_payroll.display) return;
		frm.__tagihan_payroll_ditawarkan = true;

		me.ambil_tagihan(frm.doc.no_payroll_entry).then((data) => {
			const tagihan = data.tagihan || [];
			const terpilih = new Set((frm.doc.rincian_payroll || []).map((d) => me.kunci(d)));

			const d = new frappe.ui.Dialog({
				title: __("Pilih Tagihan — {0}", [frm.doc.no_payroll_entry]),
				size: "extra-large",
				fields: [{ fieldtype: "HTML", fieldname: "tabel" }],
				primary_action_label: __("Pakai"),
				primary_action() {
					const dipilih = [];
					d.$wrapper.find(".pilih-baris:checked").each(function () {
						dipilih.push(tagihan[cint($(this).attr("data-idx"))]);
					});
					if (!dipilih.length) {
						frappe.msgprint(__("Belum ada tagihan yang dipilih."));
						return;
					}

					frm.clear_table("rincian_payroll");
					dipilih.forEach((t) => {
						frm.add_child("rincian_payroll", {
							tipe: t.tipe,
							sub_tipe: t.sub_tipe,
							account: t.account,
							party_type: t.party_type,
							party: t.party,
							tagihan: t.tagihan,
							sisa: t.sisa,
							amount: t.sisa,
						});
					});
					frm.set_value("paid_to", dipilih[0].account);
					me.hitung_total(frm);
					frm.refresh_field("rincian_payroll");
					d.hide();
				},
			});

			frm.__dialog_tagihan_payroll = d;
			d.fields_dict.tabel.$wrapper.html(me.tabel_tagihan(tagihan, { pilih: true, terpilih }));
			d.$wrapper.on("change", ".pilih-tipe", function () {
				const tipe = $(this).attr("data-tipe");
				d.$wrapper
					.find(`.pilih-baris[data-tipe="${tipe}"]`)
					.prop("checked", $(this).prop("checked"));
			});
			d.$wrapper.on("click", ".lihat-dokumen", function () {
				const t = tagihan[cint($(this).attr("data-idx"))];
				me.lihat_dokumen(frm.doc.no_payroll_entry, [t]);
			});
			d.show();
		});
	},

	hitung_total(frm) {
		const total = (frm.doc.rincian_payroll || []).reduce((s, d) => s + flt(d.amount), 0);
		frm.set_value("paid_amount", total);
		frm.set_value("received_amount", total);
	},

	// Dipanggil dari Payroll Entry: tagihan per tipe, yang sudah dibayar, dan
	// Payment Entry yang membayarnya.
	lihat_rincian(frm) {
		const me = this;
		me.ambil_tagihan(frm.doc.name).then((data) => {
			const tagihan = data.tagihan || [];
			const d = new frappe.ui.Dialog({
				title: __("Rincian Pembayaran — {0}", [frm.doc.name]),
				size: "extra-large",
				fields: [
					{ fieldtype: "HTML", fieldname: "tabel" },
					{ fieldtype: "Section Break", label: __("Payment Entry") },
					{ fieldtype: "HTML", fieldname: "pembayaran" },
				],
			});
			d.fields_dict.tabel.$wrapper.html(me.tabel_tagihan(tagihan));
			d.fields_dict.pembayaran.$wrapper.html(me.tabel_pembayaran(data.pembayaran || []));
			d.$wrapper.on("click", ".lihat-dokumen", function () {
				me.lihat_dokumen(frm.doc.name, [tagihan[cint($(this).attr("data-idx"))]]);
			});
			d.show();
		});
	},

	// Dokumen asal tiap tagihan: Employee Potongan, Daftar BPJS beserta BPJS
	// TK/KES-nya, Additional Salary, dan rincian per karyawan dari slipnya.
	lihat_dokumen(payroll_entry, daftar_tagihan) {
		const me = this;
		const esc = frappe.utils.escape_html;

		frappe
			.call({
				method: `${me.METHOD}.get_dokumen_terkait`,
				args: {
					payroll_entry,
					kunci_tagihan: JSON.stringify(
						daftar_tagihan.map((t) => [t.tipe, t.sub_tipe || "", t.account])
					),
				},
				freeze: true,
			})
			.then((r) => {
				const kelompok = r.message || [];
				if (!kelompok.length) {
					frappe.msgprint(__("Tidak ada dokumen untuk tagihan ini."));
					return;
				}

				const html = kelompok
					.map((g) => {
						const dokumen = g.dokumen.length
							? `<table class="table table-bordered table-condensed">
								<thead style="background:var(--subtle-fg)"><tr>
									<th>${__("Dokumen")}</th><th>${__("Dokumen BPJS")}</th>
									<th style="text-align:right">${__("Karyawan")}</th>
									<th style="text-align:right">${__("Jumlah")}</th>
								</tr></thead>
								<tbody>${g.dokumen
									.map((d) => `<tr>
										<td><span class="text-muted">${esc(d.doctype)}</span> ${me.tautan(d.doctype, d.name)}</td>
										<td>${d.dokumen_bpjs ? me.tautan(g.sub_tipe, d.dokumen_bpjs) : ""}</td>
										<td style="text-align:right">${d.karyawan}</td>
										<td style="text-align:right">${me.uang(d.jumlah)}</td>
									</tr>`)
									.join("")}</tbody>
							</table>`
							: "";

						const karyawan = `<details>
							<summary>${__("Rincian per karyawan ({0} baris)", [g.karyawan.length])}</summary>
							<table class="table table-bordered table-condensed" style="margin-top:6px">
								<thead style="background:var(--subtle-fg)"><tr>
									<th>${__("Karyawan")}</th><th>${__("Salary Slip")}</th>
									<th>${__("Komponen")}</th><th>${__("Sumber")}</th>
									<th style="text-align:right">${__("Jumlah")}</th>
								</tr></thead>
								<tbody>${g.karyawan
									.map((k) => `<tr>
										<td>${esc(k.employee_name || k.employee)}<br><small class="text-muted">${esc(k.employee)}</small></td>
										<td>${me.tautan("Salary Slip", k.salary_slip)}</td>
										<td>${esc(k.salary_component || __("Net Pay"))}</td>
										<td>${k.sumber_doctype === "Salary Slip" ? "" : `<span class="text-muted">${esc(k.sumber_doctype)}</span> ${me.tautan(k.sumber_doctype, k.sumber)}`}</td>
										<td style="text-align:right">${me.uang(k.amount)}</td>
									</tr>`)
									.join("")}</tbody>
							</table>
						</details>`;

						return `<h5 style="margin-top:14px">${me.label_tipe(g)}
							<span class="text-muted small">${esc(g.account || "")}</span>
							<span style="float:right">${me.uang(g.jumlah)}</span></h5>
							${dokumen}${karyawan}`;
					})
					.join("<hr>");

				const d = new frappe.ui.Dialog({
					title: __("Dokumen Terkait — {0}", [payroll_entry]),
					size: "extra-large",
				});
				d.body.innerHTML = html;
				d.show();
			});
	},
});
