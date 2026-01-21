
frappe.ui.form.on('Contract Template', {
    refresh: function(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__('Download PDF'), function() {
                // Use window.open to download PDF
                var url = `/api/method/sth.overrides.contract_template.download_contract_pdf`;
                url += `?doctype=${encodeURIComponent(frm.doc.doctype)}&docname=${encodeURIComponent(frm.doc.name)}&print_format=${encodeURIComponent("Contract Terms")}`

                window.open(url, '_blank');
                
                frappe.show_alert({
                    message: __('Downloading PDF...'),
                    indicator: 'green'
                });
            });
        }
    }
});