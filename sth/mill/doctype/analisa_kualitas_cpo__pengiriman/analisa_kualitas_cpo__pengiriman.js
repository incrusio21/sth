frappe.ui.form.on('Analisa Kualitas CPO  Pengiriman', {
    refresh(frm) {
        // Pre-fetch ticket_numbers from Timbangan, then set the query filter
        frappe.db.get_list('Timbangan', {
            fields: ['ticket_number'],
            filters: [['ticket_number', '!=', '']],
            limit: 0
        }).then(data => {
            const ticket_numbers = [...new Set(data.map(d => d.ticket_number))];

            frm.set_query('ticket_number', function() {
                return {
                    filters: [
                        ['name', 'in', ticket_numbers],
                        ['transaction_type','=','Dispatch']
                    ]
                };
            });
        });
    }
});