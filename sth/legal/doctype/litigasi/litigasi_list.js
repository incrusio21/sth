frappe.listview_settings["Litigasi"] = {
	add_fields: [
		"status",
	],
	get_indicator: function (doc) {
		// Please do not add precision in the flt function
		if (doc.status === "Selesai") {
			return [__("Selesai"), "green", "status,=,Selesai"];
		}else if (doc.status === "Berjalan") {
			return [__("Berjalan"), "orange", "status,=,Berjalan"];
		}
	},
};
