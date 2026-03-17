frappe.ui.form.off("Leave Application", "make_dashboard");
frappe.ui.form.off("Leave Application", "get_leave_balance");

frappe.ui.form.on("Leave Application", {
	make_dashboard: function (frm) {
		let leave_details;
		let lwps;

		if (frm.doc.employee) {
			frappe.call({
				method: "sth.overrides.leave_application.get_leave_details_custom",
				async: false,
				args: {
					employee: frm.doc.employee,
					date: frm.doc.from_date || frm.doc.posting_date,
				},
				callback: function (r) {
					if (!r.exc && r.message["leave_allocation"]) {
						leave_details = r.message["leave_allocation"];
					}
					lwps = r.message["lwps"];
				},
			});

			$("div").remove(".form-dashboard-section.custom");

			frm.dashboard.add_section(
				frappe.render_template("leave_application_dashboard", {
					data: leave_details,
				}),
				__("Allocated Leaves"),
			);
			frm.dashboard.show();

			let allowed_leave_types = Object.keys(leave_details);
			// lwps should be allowed for selection as they don't have any allocation
			allowed_leave_types = allowed_leave_types.concat(lwps);

			frm.set_query("leave_type", function () {
				return {
					filters: [["leave_type_name", "in", allowed_leave_types]],
				};
			});
		}
	},
	get_leave_balance: function (frm) {
		if (
			frm.doc.docstatus === 0 &&
			frm.doc.employee &&
			frm.doc.leave_type &&
			frm.doc.from_date &&
			frm.doc.to_date
		) {
			return frappe.call({
				method: "sth.overrides.leave_application.get_leave_balance_on_custom",
				args: {
					employee: frm.doc.employee,
					date: frm.doc.from_date,
					to_date: frm.doc.to_date,
					leave_type: frm.doc.leave_type,
					consider_all_leaves_in_the_allocation_period: 1,
				},
				callback: function (r) {
					if (!r.exc && r.message) {
						frm.set_value("leave_balance", r.message);
					} else {
						frm.set_value("leave_balance", "0");
					}
				},
			});
		}
	},
});