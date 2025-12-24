// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.listview_settings["Attendance"] = {
    onload: function (list_view) {
		let me = this;

		list_view.page.add_inner_button(__("Re-calculate Premi"), function () {
			let first_day_of_month = moment().startOf("month");

			if (moment().toDate().getDate() === 1) {
				first_day_of_month = first_day_of_month.subtract(1, "month");
			}

			let dialog = new frappe.ui.Dialog({
				title: __("Re-calculate Premi"),
				fields: [
					{
						label: __("Start"),
						fieldtype: "Date",
						fieldname: "from_date",
						reqd: 1,
						default: first_day_of_month.toDate(),
					},
					{
						fieldtype: "Column Break",
						fieldname: "time_period_column",
					},
					{
						label: __("End"),
						fieldtype: "Date",
						fieldname: "to_date",
						reqd: 1,
						default: moment().toDate(),
					}
				],
				primary_action(data) {
					frappe.call({
						method: "sth.hr_customize.update_payment_log",
						args: {
							voucher_type: "Attendance",
							filters: {
								attendance_date: ["between", [data.from_date, data.to_date]]
							}
						},
						frezee: true,
						callback: function (r) {
							if (r.message === 1) {
								frappe.show_alert({
									message: __("Attendance Marked"),
									indicator: "blue",
								});
								cur_dialog.hide();
							}
						},
					});
					dialog.hide();
					list_view.refresh();
				},
				primary_action_label: __("Submit"),
			});
			dialog.show();
		});
	}
};