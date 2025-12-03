frappe.ui.form.on('Driver', {
    refresh(frm) {
        if (frm.doc.custom_qr) {
            render_qr(frm);
        }
    }
});

function render_qr(frm) {
    if (!frm.doc.custom_qr) return;

    const html = `
        <div style="padding: 8px 0;">
            <img 
                src="data:image/svg+xml;base64,${frm.doc.custom_qr}" 
                alt="QR Code" 
                style="width: 140px; height: 140px;"
            />
        </div>
    `;

    frm.get_field('custom_qr_preview').$wrapper.html(html);
}