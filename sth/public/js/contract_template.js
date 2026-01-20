
frappe.ui.form.on('Contract Template', {
    refresh: function(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__('Download PDF'), function() {
                // Use window.open to download PDF
                const url = `/api/method/sth.overrides.contract_template.download_contract_pdf?docname=${encodeURIComponent(frm.doc.name)}`;
                window.open(url, '_blank');
                
                frappe.show_alert({
                    message: __('Downloading PDF...'),
                    indicator: 'green'
                });
            });
        }
    }
});