// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

sth.form.override_class_function(frappe.listview_settings["Attendance"], "onload", function() {
	let me = this;

	cur_list.page.add_inner_button(__("Re-calculate Premi"), function () {
		sth.form.recalculate_payment_log("Attendance", "attendance_date")
	});
})