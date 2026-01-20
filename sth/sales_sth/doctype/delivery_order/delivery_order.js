

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
						per_delivered: ["<", 99.99],
						company: frm.doc.company
					}
				});
			}, __("Get Items From"));
		}

		if (frm.doc.docstatus == 1) {
			if (frm.doc.delivery_order_transporter && frm.doc.delivery_order_transporter.length > 0) {
				frm.add_custom_button(__('Delivery Note'), function() {
					show_transporter_dialog(frm);
				}, __('Create'));
			} else {
				frm.add_custom_button(__('Delivery Note'), function() {
					create_delivery_note(frm, null);
				}, __('Create'));
			}
		}
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