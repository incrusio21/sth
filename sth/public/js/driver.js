frappe.ui.form.on('Driver', {
    refresh(frm) {
        if (frm.doc.custom_qr) {
            render_qr(frm);
        }

        if (!frm.is_new()) {
            frm.add_custom_button(__('Generate QR'), () => {
                generate_and_render_qr(frm);
            });
        }
    }
});

function generate_and_render_qr(frm) {
    frappe.call({
        method: 'sth.utils.qr_generator.generate_qr_for_doc',
        args: {
            doctype: frm.doctype,
            docname: frm.doc.name,
            fieldname: null
        },
        callback(r) {
            if (!r.exc && r.message) {
                frm.doc.custom_qr = r.message;
                frm.refresh_field('custom_qr');

                render_qr(frm);
            }
        }
    });
}

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