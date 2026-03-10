frappe.ui.form.on("Company", {
	refresh(frm) {
		apply_account_filters(frm);
	},
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