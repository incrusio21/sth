

frappe.ui.form.on('Delivery Order', {
	refresh: function(frm) {
		if (frm.doc.docstatus == 0) {
			frm.add_custom_button(__('Sales Order'), function() {
				erpnext.utils.map_current_doc({
					method: "sth.sales_sth.custom.sales_order.make_delivery_order",
					source_doctype: "Sales Order",
					target: frm,
					setters: {
						customer: frm.doc.customer || undefined,
						company: frm.doc.company || undefined
					},
					get_query_filters: {
						docstatus: 1,
						status: ["not in", ["Closed", "On Hold"]],
						per_delivery_ordered: ["<", 99.99],
						company: frm.doc.company
					}
				});
			}, __("Get Items From"));
		}

		if (frm.doc.docstatus == 1) {
			if (frm.doc.delivery_order_transporter && frm.doc.delivery_order_transporter.length > 0) {
				// frm.add_custom_button(__('Delivery Note'), function() {
				// 	show_transporter_dialog(frm);
				// }, __('Create'));
			} else {
				// frm.add_custom_button(__('Delivery Note'), function() {
				// 	create_delivery_note(frm, null);
				// }, __('Create'));
			}
		}
        
        frm.set_query('driver', 'delivery_order_transporter', function(doc, cdt, cdn) {
            let row = locals[cdt][cdn];
            if (row.transporter) {
                return {
                    filters: {
                        'transporter': row.transporter

                    }
                };
            }
        });

		if (!frm.is_new() && (frm.doc.delivery_order_transporter || []).length) {
			frm.add_custom_button(__('Terbitkan QR Kedaluwarsa'), function() {
				frm.events.buat_ulang_qr(frm, 0);
			}, __('QR Transporter'));

			frm.add_custom_button(__('Terbitkan Ulang Semua QR'), function() {
				frappe.confirm(
					__('QR lama semua baris langsung mati, termasuk yang sudah dipegang sopir. Lanjutkan?'),
					function() { frm.events.buat_ulang_qr(frm, 1); }
				);
			}, __('QR Transporter'));
		}

	},

	buat_ulang_qr: function(frm, semua) {
		frappe.call({
			method: 'sth.sales_sth.doctype.delivery_order.delivery_order.buat_ulang_qr_transporter',
			args: { delivery_order: frm.doc.name, semua: semua },
			freeze: true,
			freeze_message: __('Menerbitkan QR...')
		}).then(function(r) {
			if (!r.message) return;

			frappe.show_alert({
				message: __('{0} dari {1} baris transporter dapat QR baru.', [r.message.diperbarui, r.message.total]),
				indicator: r.message.diperbarui ? 'green' : 'orange'
			}, 5);

			frm.reload_doc();
		});
	},

	render_qr_transporter: function(row, wrapper) {
		if (!row.qr_code) {
			$(wrapper).html(`<div class="text-muted">${__('Belum ada QR. Simpan Delivery Order atau pakai tombol QR Transporter.')}</div>`);
			return;
		}

		const kedaluwarsa = row.qr_berlaku_sampai && frappe.datetime.now_datetime() > row.qr_berlaku_sampai;
		const batas = row.qr_berlaku_sampai ? frappe.datetime.str_to_user(row.qr_berlaku_sampai) : '-';
		const catatan = kedaluwarsa
			? `<div class="text-danger">${__('QR kedaluwarsa {0}', [batas])}</div>`
			: `<div class="text-muted">${__('Berlaku sampai {0}', [batas])}</div>`;

		$(wrapper).html(`
			<div style="padding: 8px 0;">
				<img
					src="data:image/svg+xml;base64,${row.qr_code}"
					alt="QR Code"
					style="width: 140px; height: 140px;${kedaluwarsa ? ' opacity: 0.35;' : ''}"
				/>
				${catatan}
			</div>
		`);
	}
});

function show_transporter_dialog(frm) {
    let transporter_options = [];
    let transporter_map = {};
    
    frm.doc.delivery_order_transporter.forEach(function(row) {
        let label = row.transporter_name || row.transporter;
        if (row.vehicle_no) {
            label += ' - ' + row.vehicle_no;
        }
        
        transporter_options.push({
            label: label,
            value: row.name
        });
        
        transporter_map[row.name] = row;
    });
    
    let d = new frappe.ui.Dialog({
        title: __('Select Transporter for Delivery Note'),
        fields: [
            {
                label: __('Transporter'),
                fieldname: 'transporter_row',
                fieldtype: 'Select',
                options: transporter_options,
                reqd: 1,
                description: __('Select which transporter will be used for this Delivery Note')
            },
            {
                fieldname: 'section_break',
                fieldtype: 'Section Break'
            },
            {
                label: __('Transporter Details'),
                fieldname: 'transporter_details',
                fieldtype: 'HTML',
                options: '<div id="transporter-info"></div>'
            }
        ],
        primary_action_label: __('Create Delivery Note'),
        primary_action: function(values) {
            let selected_transporter = transporter_map[values.transporter_row];
            create_delivery_note(frm, selected_transporter);
            d.hide();
        }
    });
    
    d.fields_dict.transporter_row.$input.on('change', function() {
        let selected = d.get_value('transporter_row');
        if (selected && transporter_map[selected]) {
            let trans = transporter_map[selected];
            let html = `
                <table class="table table-bordered" style="margin-top: 10px;">
                    <tr>
                        <td style="width: 40%;"><strong>Transporter</strong></td>
                        <td>${trans.transporter || '-'}</td>
                    </tr>
                    <tr>
                        <td><strong>Transporter Name</strong></td>
                        <td>${trans.transporter_name || '-'}</td>
                    </tr>
                    <tr>
                        <td><strong>Vehicle No</strong></td>
                        <td>${trans.vehicle_no || '-'}</td>
                    </tr>
                    <tr>
                        <td><strong>Driver Name</strong></td>
                        <td>${trans.driver_name || '-'}</td>
                    </tr>
                    <tr>
                        <td><strong>Driver Contact</strong></td>
                        <td>${trans.driver_contact || '-'}</td>
                    </tr>
                </table>
            `;
            d.fields_dict.transporter_details.$wrapper.html(html);
        }
    });
    
    d.show();
    
    if (transporter_options.length > 0) {
        d.set_value('transporter_row', transporter_options[0].value);
        d.fields_dict.transporter_row.$input.trigger('change');
    }
}

function create_delivery_note(frm, transporter_data) {
    frappe.call({
        method: 'sth.sales_sth.doctype.delivery_order.delivery_order.make_delivery_note',
        args: {
            source_name: frm.doc.name,
            transporter_data: transporter_data
        },
        freeze: true,
        freeze_message: __('Creating Delivery Note...'),
        callback: function(r) {
            if (r.message) {
                frappe.model.sync(r.message);
                frappe.set_route('Form', r.message.doctype, r.message.name);
                
                frappe.show_alert({
                    message: __('Delivery Note {0} created', [r.message.name]),
                    indicator: 'green'
                }, 5);
            }
        }
    });
}

frappe.ui.form.on('Delivery Order Transporter', {
    form_render: function(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        const grid_row = frm.get_field('delivery_order_transporter').grid.grid_rows_by_docname[cdn];
        const grid_form = grid_row && grid_row.grid_form;

        if (!grid_form || !grid_form.fields_dict.qr_preview) return;

        frm.events.render_qr_transporter(row, grid_form.fields_dict.qr_preview.wrapper);
    },

    transporter: function(frm, cdt, cdn) {
        frm.set_query('driver', 'delivery_order_transporter', function(doc, cdt, cdn) {
            let row = locals[cdt][cdn];
            if (row.transporter) {
                return {
                    filters: {
                        'transporter': row.transporter
                        
                    }
                };
            }
        });
    }
});

