frappe.ui.form.on('Supplier', {
	setup: function (frm) {
		frm.set_query("user_email", "struktur_supplier", (doc) => {
			return {
				filters: {
					supplier: doc.name
				}
			}
		})

		frm.set_query("kontak_person", "alamat_dan_pic_supplier", (doc) => {
			return {
				filters: {
					supplier: doc.name
				}
			}
		})
	},
	onload: function (frm) {
		if (frm.is_new() && !frm.doc.kode_supplier) {
			generate_kode_supplier(frm);
		}
		hide_details(frm)

	},
	refresh: function (frm) {
		if (frm.is_new()) {
			frm.set_value('aktif', 1); // Set checkbox checked by default
			frm.set_value('default', 'Ya');
			frm.set_value('status_bank', 'Aktif');
		}

		check_status_pkp(frm)
		hide_details(frm)
	},
	aktif: function (frm) {
		if (frm.doc.aktif) {
			frm.set_value('default', 'Ya');
			frm.set_value('status_bank', 'Aktif');
		} else {
			frm.set_value('default', 'Tidak');
			frm.set_value('status_bank', 'Tidak Aktif');
		}
	},
	status_pkp: function (frm) {
		check_status_pkp(frm)
	},
	badan_usaha: async function(frm) {
		await update_kriteria_type(frm);
	}
});

function generate_kode_supplier(frm) {
	frappe.call({
		method: 'sth.overrides.supplier.get_next_supplier',
		callback: function (r) {
			if (r.message) {
				frm.set_value('kode_supplier', r.message);
			}
		}
	});
}

function check_status_pkp(frm) {
	if (frm.doc.status_pkp) {
		frm.set_df_property('no_sppkp', 'read_only', 0);
	} else {
		frm.set_df_property('no_sppkp', 'read_only', 1);
	}
}

function hide_details(frm) {
	frm.set_df_property('section_break_vmze3', 'hidden', 1);
	frm.set_df_property('section_break_d3qta', 'hidden', 1);
	frm.set_df_property('section_break_1lvsu', 'hidden', 1);
	frm.set_df_property('section_break_vrfr5', 'hidden', 1);
	frm.set_df_property('pajak_label', 'hidden', 1);
	frm.set_df_property('section_break_6doas', 'hidden', 1);

	frm.set_df_property('kode_supplier', 'read_only', 1);

}

frappe.ui.form.on('Struktur Supplier', {
	add_jenis_usaha: function (frm, cdt, cdn) {
		let row = locals[cdt][cdn];

		let d = new frappe.ui.Dialog({
			title: __('Select Item Groups'),
			fields: [
				{
					fieldname: 'item_groups',
					fieldtype: 'MultiSelectList',
					label: __('Item Groups'),
					options: [],
					get_data: function () {
						return frappe.call({
							method: 'frappe.client.get_list',
							args: {
								doctype: 'Item Group',
								filters: {
									is_group: 1
								},
								fields: ['item_group_name', 'name'],
								order_by: 'name asc',
								limit_page_length: 0
							}
						}).then(r => {
							return r.message.map(item => ({
								value: item.item_group_name,
								description: item.name
							}));
						});
					}
				}
			],
			primary_action_label: __('Select'),
			primary_action: function (values) {
				if (values.item_groups && values.item_groups.length > 0) {
					let selected_groups = values.item_groups.join(', ');

					frappe.model.set_value(cdt, cdn, 'jenis_usaha', selected_groups);

					frm.refresh_field('struktur_supplier');
				}
				d.hide();
			}
		});

		if (row.jenis_usaha) {
			let existing_values = row.jenis_usaha.split(',').map(v => v.trim());
			d.fields_dict.item_groups.df.default = existing_values;
		}

		d.show();
	}
});

frappe.ui.form.on("NPWP dan SPPKP Supplier", {
	status_pkp: async function(frm, cdt, cdn) {
		await update_kriteria_type(frm);
	}
});

async function update_kriteria_type(frm) {
	// Skip if new or unsaved
	if (frm.is_new()) return;

	let skip_sppkp = "Not SPPKP";
	let badan_usaha = "Non Koperasi";

	if ((frm.doc.npwp_dan_sppkp_supplier || []).some(row => row.status_pkp)) {
		skip_sppkp = "SPPKP";
	}
	if (frm.doc.badan_usaha == "Koperasi") {
		badan_usaha = "Koperasi";
	}
	if (frm.doc.badan_usaha == "PT" || frm.doc.badan_usaha == "CV") {
		badan_usaha = "PT";
	}

	const kriteria_type = badan_usaha + "-" + skip_sppkp;

	await frappe.call({
		method: "sth.finance_sth.doctype.kriteria_dokumen_finance.kriteria_dokumen_finance.update_criteria_type",
		freeze: true,
		freeze_message: __("Updating criteria..."),
		args: {
			voucher_type: frm.doc.doctype,
			voucher_no: frm.doc.name,
			document_type: kriteria_type,
		},
	});

	render_kriteria_upload(frm);

	frappe.show_alert({
		message: __(`Kriteria updated to: ${kriteria_type}`),
		indicator: "blue"
	});
}

async function render_kriteria_upload(frm) {
	const $wrapper = $(frm.fields_dict['kriteria_upload_html'].wrapper);
	const voucher_type = frm.doctype;
	const voucher_no = frm.doc.name;

	$wrapper.html(`
		<div style="padding:10px 0; color:#8D99AE; font-size:12px; font-family:monospace;">
			⏳ Loading upload documents...
		</div>
	`);

	try {
		const result = await frappe.db.get_list('Kriteria Upload Document', {
			filters: {
				voucher_type: voucher_type,
				voucher_no: voucher_no
			},
			fields: ['name'],
			limit: 1
		});

		if (!result || result.length === 0) {
			$wrapper.html(`
				<div style="
					background:#f8f9fa; border:1px dashed #dee2e6; border-radius:6px;
					padding:12px 16px; color:#8D99AE; font-size:12px;
				">
					No Kriteria Upload Document found for this record.
				</div>
			`);
			return;
		}

		const doc_name = result[0].name;
		const doc = await frappe.db.get_doc('Kriteria Upload Document', doc_name);
		const rows = doc.file_upload || [];

		if (rows.length === 0) {
			$wrapper.html(`
				<div style="
					background:#f8f9fa; border:1px dashed #dee2e6; border-radius:6px;
					padding:12px 16px; color:#8D99AE; font-size:12px;
				">
					Document found (<b>${doc_name}</b>) but no files uploaded yet.
				</div>
			`);
			return;
		}

		$wrapper.html(build_table_html(doc_name, rows));

	} catch (err) {
		$wrapper.html(`
			<div style="
				background:#FFF5F5; border:1px solid #FFC5C5; border-radius:6px;
				padding:12px 16px; color:#c0392b; font-size:12px;
			">
				❌ Error: ${err.message || err}
			</div>
		`);
		console.error('[Kriteria Upload] Error:', err);
	}
}


function build_table_html(doc_name, rows) {
	const rows_html = rows.map((row, idx) => {
		const file_url = resolve_file_url(row.upload_file);
		const file_cell = file_url
			? `<a href="${file_url}" target="_blank" rel="noopener noreferrer" style="
					display:inline-flex; align-items:center; gap:5px;
					background:#EBF3FF; border:1px solid #B8D4FF; border-radius:4px;
					color:#1a73e8; font-size:12px; padding:4px 10px;
					text-decoration:none; font-weight:500;
			   ">${file_icon()} View File</a>`
			: `<span style="color:#aaa; font-style:italic; font-size:12px;">No file</span>`;

		return `
			<tr style="border-bottom:1px solid #f0f0f0;">
				<td style="padding:10px 12px; color:#aaa; font-size:12px; width:40px;">${idx + 1}</td>
				<td style="padding:10px 12px; font-size:13px; color:#333;">
					${frappe.utils.escape_html(row.rincian_dokumen_finance || '—')}
				</td>
				<td style="padding:10px 12px;">${file_cell}</td>
			</tr>
		`;
	}).join('');

	return `
		<div style="margin: 4px 0 12px;">
			<div style="
				display:flex; align-items:center; justify-content:space-between;
				margin-bottom:8px;
			">
				<span style="font-size:12px; font-weight:600; color:#555;
							 text-transform:uppercase; letter-spacing:0.05em;">
					Dokumen
				</span>
				<!-- ini buat link ke Kriteria Upload Document
				<a href="/app/kriteria-upload-document/${encodeURIComponent(doc_name)}"
					target="_blank"
					style="font-size:11px; color:#1a73e8; text-decoration:none;">
					Open Document ↗
				</a> -->
			</div>
			<div style="border:1px solid #e4e4e4; border-radius:6px; overflow:hidden; background:#fff;">
				<table style="width:100%; border-collapse:collapse;">
					<thead>
						<tr style="background:#f8f9fa; border-bottom:1px solid #e4e4e4;">
							<th style="padding:9px 12px; text-align:left; font-size:11px;
									   color:#888; font-weight:500; width:40px;">#</th>
							<th style="padding:9px 12px; text-align:left; font-size:11px;
									   color:#888; font-weight:500;">Rincian Dokumen Finance</th>
							<th style="padding:9px 12px; text-align:left; font-size:11px;
									   color:#888; font-weight:500; width:120px;">File</th>
						</tr>
					</thead>
					<tbody>${rows_html}</tbody>
				</table>
			</div>
		</div>
	`;
}

function resolve_file_url(file_path) {
	if (!file_path) return null;
	if (file_path.startsWith('http://') || file_path.startsWith('https://')) return file_path;
	return window.location.origin + file_path;
}

function file_icon() {
	return `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
				stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
				<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
				<polyline points="14 2 14 8 20 8"/>
			</svg>`;
}