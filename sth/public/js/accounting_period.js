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
	},
	unit(frm) {
		sesuaikan_dokumen_mill(frm);
	}
});

// Grid Closed Documents sudah terisi di onload, sebelum unitnya dipilih. Dokumen
// pabrik cuma berlaku untuk unit yang dicentang Mill, jadi begitu unitnya
// diketahui barisnya dibuang — atau dikembalikan kalau sebelumnya sempat dibuang
// untuk unit lain. Sisi server membuangnya lagi waktu validate; ini supaya yang
// dilihat sama dengan yang nanti tersimpan.
function sesuaikan_dokumen_mill(frm) {
	if (!frm.doc.unit) {
		return;
	}

	frappe.call({
		method: "sth.overrides.accounting_period.dokumen_mill_untuk_unit",
		args: { unit: frm.doc.unit }
	}).then((r) => {
		if (!r.message) {
			return;
		}

		const mill = new Set(r.message.doctype);
		const semula = (frm.doc.closed_documents || []).map((row) => ({
			document_type: row.document_type,
			closed: row.closed
		}));

		let hasil;
		if (r.message.berlaku) {
			const ada = new Set(semula.map((row) => row.document_type));
			const kurang = [...mill].filter((doctype) => !ada.has(doctype));
			// closed 1 sama dengan bawaan get_doctypes_for_closing ERPNext.
			hasil = semula.concat(kurang.map((doctype) => ({ document_type: doctype, closed: 1 })));
		} else {
			hasil = semula.filter((row) => !mill.has(row.document_type));
		}

		if (hasil.length === semula.length) {
			return;
		}

		frm.clear_table("closed_documents");
		hasil.forEach((row) => frm.add_child("closed_documents", row));
		frm.refresh_field("closed_documents");
	});
}

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