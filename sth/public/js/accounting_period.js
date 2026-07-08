frappe.ui.form.on('Accounting Period', {
	refresh(frm) {
		set_unit_filter(frm);

		if (frm.doc.workflow_state === "Submitted" && !frm.is_new()) {
			frm.add_custom_button(__("Lihat Report Summary"), () => {
				lihat_report_summary_bengkel(frm);
			});

			frm.add_custom_button(__("Lihat GL Entry"), () => {
				lihat_gl_entry_bengkel(frm);
			});
		}
	},
	company(frm) {
		set_unit_filter(frm);
	}
});

function lihat_report_summary_bengkel(frm) {
	frappe.db.get_value("Costing Bengkel", {
		company: frm.doc.company,
		unit: frm.doc.unit,
		periode_dari: frm.doc.start_date,
		periode_sampai: frm.doc.end_date,
		docstatus: ["!=", 2]
	}, "name").then(({ message }) => {
		if (!message || !message.name) {
			frappe.msgprint(__("Costing Bengkel untuk periode ini belum ditemukan."));
			return;
		}

		frappe.set_route("query-report", "Costing Bengkel Summary", {
			costing_bengkel: message.name
		});
	});
}

function lihat_gl_entry_bengkel(frm) {
	frappe.db.get_value("Costing Bengkel", {
		company: frm.doc.company,
		unit: frm.doc.unit,
		periode_dari: frm.doc.start_date,
		periode_sampai: frm.doc.end_date,
		docstatus: ["!=", 2]
	}, "name").then(({ message }) => {
		if (!message || !message.name) {
			frappe.msgprint(__("Costing Bengkel untuk periode ini belum ditemukan."));
			return;
		}

		frappe.set_route("query-report", "General Ledger", {
			company: frm.doc.company,
			from_date: frm.doc.start_date,
			to_date: frm.doc.end_date,
			voucher_no: message.name
		});
	});
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