
$(document).on('form-refresh', function(e, frm) {
	// Skip unsaved docs
	if (frm.is_new()) return;

	// Only proceed if this doctype has the sentinel field
	if (!frm.fields_dict['kriteria_upload_html']) return;

	render_kriteria_upload(frm);
});


async function render_kriteria_upload(frm) {
	const $wrapper     = $(frm.fields_dict['kriteria_upload_html'].wrapper);
	const voucher_type = frm.doctype;
	const voucher_no   = frm.doc.name;

	$wrapper.html(`
		<div style="padding:10px 0; color:#8D99AE; font-size:12px; font-family:monospace;">
			⏳ Loading upload documents...
		</div>
	`);

	try {
		const result = await frappe.db.get_list('Kriteria Upload Document', {
			filters: {
				voucher_type: voucher_type,
				voucher_no:   voucher_no
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
		const doc      = await frappe.db.get_doc('Kriteria Upload Document', doc_name);
		const rows     = doc.file_upload || [];

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

	} catch(err) {
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
		const file_url  = resolve_file_url(row.upload_file);
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