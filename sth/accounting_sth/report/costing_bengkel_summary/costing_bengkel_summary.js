frappe.query_reports["Costing Bengkel Summary"] = {
    filters: [
        {
            fieldname: "costing_bengkel",
            label: __("No Costing Bengkel"),
            fieldtype: "Link",
            options: "Costing Bengkel",
            on_change(report) {
                fill_from_costing_bengkel(report);
            }
        },
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            read_only: 1
        },
        {
            fieldname: "unit",
            label: __("Unit"),
            fieldtype: "Link",
            options: "Unit",
            read_only: 1
        },
        {
            fieldname: "from_date",
            label: __("Periode Dari"),
            fieldtype: "Date",
            read_only: 1
        },
        {
            fieldname: "to_date",
            label: __("Periode Sampai"),
            fieldtype: "Date",
            read_only: 1
        }
    ],

    onload(report) {
        fill_from_costing_bengkel(report);
    }
};

function fill_from_costing_bengkel(report) {
    const costing_bengkel = frappe.query_report.get_filter_value("costing_bengkel");

    if (!costing_bengkel) {
        frappe.query_report.set_filter_value("company", "");
        frappe.query_report.set_filter_value("unit", "");
        frappe.query_report.set_filter_value("from_date", "");
        frappe.query_report.set_filter_value("to_date", "");
        report.page.clear_indicator();
        return;
    }

    frappe.db.get_value("Costing Bengkel", costing_bengkel, ["company", "unit", "periode_dari", "periode_sampai"]).then(({ message }) => {
        if (!message) return;
        frappe.query_report.set_filter_value("company", message.company || "");
        frappe.query_report.set_filter_value("unit", message.unit || "");
        frappe.query_report.set_filter_value("from_date", message.periode_dari || "");
        frappe.query_report.set_filter_value("to_date", message.periode_sampai || "");
        report.page.set_indicator(__("Costing Bengkel: {0}", [costing_bengkel]), "blue");
    });
}
