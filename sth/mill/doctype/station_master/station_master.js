// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Station Master', {
	refresh(frm) {
		// if (frm.doc.qr) {
		// 	render_qr(frm);
		// }
		frm.set_query("account", "station_procurement_settings", function (doc, cdt, cdn) {
			let row = locals[cdt][cdn];

			return {
				filters: {
					company: row.company,
					is_group: 1,
					name: ["like", "630%"]
				}
			};
		});
	},

	render_qr(qr_code, field_wrapper) {
		const html = `
		<div style="padding: 8px 0;">
			<img 
				src="data:image/svg+xml;base64,${qr_code}" 
				alt="QR Code" 
				style="width: 140px; height: 140px;"
			/>
		</div>
	`;
		$(field_wrapper).html(html);
	}
});

frappe.ui.form.on('Detail Station Master', {
	form_render(frm, dt, dn) {
		const row = locals[dt][dn]

		console.log("form opened");
		const grid_form = frm.get_field('detail_station_settings').grid.grid_rows_by_docname[dn].grid_form
		if (grid_form) {
			const wrapper = grid_form.fields_dict.qr_preview.wrapper
			frm.events.render_qr(row.qr_code, wrapper)
		}
	}
})

function render_qr(frm) {
	if (!frm.doc.qr) return;

	const html = `
		<div style="padding: 8px 0;">
			<img 
				src="data:image/svg+xml;base64,${frm.doc.qr}" 
				alt="QR Code" 
				style="width: 140px; height: 140px;"
			/>
		</div>
	`;

	frm.get_field('qr_preview').$wrapper.html(html);
}