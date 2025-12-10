frappe.ui.form.on('Asset', {
    refresh(frm) {
        if (frm.doc.qr) {
            render_qr(frm);
        }
    }
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