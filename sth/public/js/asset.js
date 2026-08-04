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

        if (frm.doc.docstatus === 1) {
            // scrap wajib lewat Asset Scrap Request (approval berlapis) dan
            // jual hanya boleh setelah discrap, jadi dua tombol bawaan
            // ERPNext ini dibuang lalu dipasang ulang sesuai status
            frm.remove_custom_button(__("Scrap Asset"), __("Manage"));
            frm.remove_custom_button(__("Sell Asset"), __("Manage"));

            setup_approval_scrap(frm);

            if (frm.doc.status === "Scrapped") {
                frm.add_custom_button(__("Sell Asset"), function() {
                    sell_asset(frm);
                }, __("Manage"));
            }

            frm.add_custom_button(__("GL Entry"), function() {
                frappe.route_options = {
                    voucher_no: frm.doc.name,
                    from_date: frm.doc.purchase_date,
                    to_date: frm.doc.purchase_date,
                    company: frm.doc.company,
                    group_by: "Group by Voucher (Consolidated)",
                };
                frappe.set_route("query-report", "General Ledger");
            }, __("View"));

            if (frm.doc.status === "Scrapped") {
                frm.add_custom_button(__("Nota Piutang"), function() {
                    make_nota_piutang(frm);
                }, __("Buat"));
            }
        }
	},
	company: function(frm) {
		frm.set_value('unit', '');
		set_unit_filter(frm);
	},
	onload: function(frm) {
		set_unit_filter(frm);
	},
});

function sell_asset(frm) {
	frappe.call({
		method: "erpnext.assets.doctype.asset.asset.make_sales_invoice",
		args: {
			asset: frm.doc.name,
			item_code: frm.doc.item_code,
			company: frm.doc.company,
			serial_no: frm.doc.serial_no
		},
		freeze: true,
		callback: function(r) {
			if (r.message) {
				const doclist = frappe.model.sync(r.message);
				frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
			}
		}
	});
}

const SCRAP_API = "sth.accounting_sth.doctype.asset_scrap_request.asset_scrap_request";

// Seluruh approval scrap dikerjakan dari form Asset. Dokumen Asset Scrap
// Request cuma pencatat di belakang layar, user tidak perlu membukanya.
function setup_approval_scrap(frm) {
	frappe.call({
		method: SCRAP_API + ".get_status_scrap",
		args: { asset: frm.doc.name },
		callback: function(r) {
			const info = r.message;
			if (!info) return;

			if (!info.name) {
				if (info.bisa_ajukan) {
					frm.add_custom_button(__("Ajukan Scrap"), function() {
						dialog_ajukan_scrap(frm);
					}, __("Manage"));
				}
				return;
			}

			frm.dashboard.add_indicator(__("Scrap: {0}", [info.workflow_state]), "orange");

			(info.actions || []).forEach(function(action) {
				frm.add_custom_button(__(action), function() {
					proses_approval_scrap(frm, action);
				}, __("Approval Scrap"));
			});
		}
	});
}

function dialog_ajukan_scrap(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Ajukan Scrap Asset"),
		fields: [
			{
				fieldname: "alasan",
				label: __("Alasan Scrap"),
				fieldtype: "Small Text",
				reqd: 1
			},
			{
				fieldname: "lampiran",
				label: __("Lampiran"),
				fieldtype: "Attach"
			}
		],
		primary_action_label: __("Ajukan"),
		primary_action(values) {
			dialog.hide();

			frappe.call({
				method: SCRAP_API + ".ajukan_scrap",
				args: {
					asset: frm.doc.name,
					alasan: values.alasan,
					lampiran: values.lampiran
				},
				freeze: true,
				freeze_message: __("Mengajukan scrap..."),
				callback: function(r) {
					frappe.show_alert({
						message: __("Pengajuan scrap dikirim ke {0}", [r.message]),
						indicator: "green"
					});
					frm.refresh();
				}
			});
		}
	});

	dialog.show();
}

function proses_approval_scrap(frm, action) {
	frappe.confirm(__("Jalankan {0} untuk pengajuan scrap asset ini?", [__(action)]), function() {
		frappe.call({
			method: SCRAP_API + ".proses_scrap",
			args: {
				asset: frm.doc.name,
				action: action
			},
			freeze: true,
			freeze_message: __("Memproses approval..."),
			callback: function(r) {
				frappe.show_alert({
					message: __("Status pengajuan sekarang: {0}", [r.message]),
					indicator: "green"
				});
				frm.reload_doc();
			}
		});
	});
}

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

function make_nota_piutang(frm) {
	frappe.db.get_list("Nota Piutang", {
		filters: {
			asset: frm.doc.name,
			docstatus: ["!=", 2],
		},
		fields: ["name"],
		limit: 1,
	}).then((existing) => {
		if (existing && existing.length) {
			frappe.msgprint(
				__("Nota Piutang {0} untuk Asset ini sudah ada.", [
					`<a href="/app/nota-piutang/${existing[0].name}">${existing[0].name}</a>`,
				])
			);
			return;
		}

		frappe.new_doc("Nota Piutang", {
			tipe: "Others",
			sub_tipe_others: "Asset",
			asset: frm.doc.name,
			company: frm.doc.company,
			date: frappe.datetime.get_today(),
		});
	});
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