frappe.listview_settings["Request for Quotation"] = {
    add_fields: ["custom_offering_status"],
    get_indicator: function (doc) {
        const status_colors = {
            Open: "yellow",
            Closed: "gray",
        };
        return [__(doc.custom_offering_status), status_colors[doc.custom_offering_status], "status,=," + doc.custom_offering_status];
    },
};
