// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.listview_settings["Attendance"] = {
    onload: function (list_view) {
		let me = this;

		list_view.page.add_inner_button(__("Re-calculate Premi"), function () {
			sth.form.recalculate_payment_log("Attendance", "attendance_date")
		});
	}
};