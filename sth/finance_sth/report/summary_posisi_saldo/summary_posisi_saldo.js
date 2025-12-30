// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Summary Posisi Saldo"] = {
	"filters": [
		{
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.add_days(frappe.datetime.get_today(), -2)
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.get_today()
        },
	]
};
