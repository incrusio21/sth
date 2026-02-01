frappe.ui.form.off('Driver', "transporter")
frappe.ui.form.on('Driver', {
    refresh(frm) {
        if (frm.doc.qr) {
            render_qr(frm);
        }
        frm.set_query("supplier", () => {
            return {
                filters: {
                    is_supplier_tbs: 1
                }
            };
        });
    },
    transporter: function (frm, cdt, cdn) {
		// // this assumes that supplier's address has same title as supplier's name
		// frappe.db
		// 	.get_doc("Address", null, { address_title: frm.doc.transporter })
		// 	.then((r) => {
		// 		frappe.model.set_value(cdt, cdn, "address", r.name);
		// 	})
		// 	.catch((err) => {
		// 		console.log(err);
		// 	});
	},
});

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