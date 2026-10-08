frappe.ui.form.on("Stock Entry", {
	setup(frm) {
		// Stock Entry Type yang tidak dicentang Is Active tidak muncul di pilihan.
		frm.set_query("stock_entry_type", () => ({
			filters: { is_active: 1 },
		}));
	},
});
