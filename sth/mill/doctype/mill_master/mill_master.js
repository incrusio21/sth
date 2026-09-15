// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mill Master", {
	refresh(frm) {
		frm.trigger("render_qr")
	},

	render_qr(frm) {
		const wrapper = frm.get_field("qr_preview").$wrapper

		if (!frm.doc.qr_code) {
			wrapper.empty()
			return
		}

		wrapper.html(`
			<div style="padding: 8px 0;">
				<img
					src="data:image/svg+xml;base64,${frm.doc.qr_code}"
					alt="QR Code"
					style="width: 140px; height: 140px;"
				/>
			</div>
		`)
	}
});
