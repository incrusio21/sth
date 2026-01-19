// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee Update Log", {
	refresh(frm) {
        if (frm.doc.status == "Failed") {
			frm.add_custom_button(__("Restart"), function () {
				frm.trigger("restart_reposting");
			}).addClass("btn-primary");
		}
	},
    restart_reposting: function (frm) {
		frappe.call({
			method: "restart_reposting",
			doc: frm.doc,
			callback: function (r) {
				frm.reload_doc();
			},
		});
	},
});
