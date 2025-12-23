frappe.ui.form.on('Asset', {
	refresh(frm) {
		if (frm.doc.qr) {
			render_qr(frm);
		}
		set_unit_filter(frm);
		frm.fields_dict.insurance_history.grid.cannot_add_rows = true;
        frm.fields_dict.insurance_history.grid.cannot_delete_rows = true;
        
        frm.fields_dict.insurance_history.grid.update_docfield_property(
            'policy_number', 'read_only', 1
        );
	},
	company: function(frm) {
		frm.set_value('unit', '');
		set_unit_filter(frm);
	},
	onload: function(frm) {
		set_unit_filter(frm);
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

function set_unit_filter(frm) {
	if (frm.doc.company) {
		frm.set_query('unit', function() {
			return {
				filters: {
					'company': frm.doc.company
				}
			};
		});
	} else {
		frm.set_query('unit', function() {
			return {};
		});
	}
}

erpnext.asset.transfer_asset = function () {
	frappe.call({
		method: "sth.overrides.asset.make_asset_movement",
		freeze: true,
		args: {
			assets: [{ name: cur_frm.doc.name }],
			purpose: "Transfer",
		},
		callback: function (r) {
			if (r.message) {
				var doc = frappe.model.sync(r.message)[0];
				frappe.set_route("Form", doc.doctype, doc.name);
			}
		},
	});
};