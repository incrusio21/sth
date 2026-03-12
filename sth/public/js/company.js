frappe.ui.form.on("Company", {
	refresh(frm) {
		apply_account_filters(frm);
	},
});

frappe.ui.form.on("Company NITKU Detail", {
	table_nitku_add(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		let npwp = frm.doc.npwp || "";

		let max = -1;

		(frm.doc.table_nitku || []).forEach(d => {
			if (d.nitku) {
				let seq = parseInt(d.nitku.slice(-6));
				if (seq > max) max = seq;
			}
		});

		let next = String(max + 1).padStart(6, "0");

		row.nitku = npwp + next;

		frm.refresh_field("table_nitku");
	}
});

function apply_account_filters(frm) {
	const account_fields = frm.meta.fields
		.filter(f => f.fieldtype === "Link" && f.options === "Account");

	account_fields.forEach(f => {
		frm.set_query(f.fieldname, () => ({
			filters: {
				company: frm.doc.name,
				is_group: 0
			}
		}));
	});
}