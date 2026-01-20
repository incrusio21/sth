// Copyright (c) 2024, Your Company and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Penerimaan TBS"] = {
    "filters": [
        {
            "fieldname": "laporan",
            "label": __("Laporan"),
            "fieldtype": "Select",
            "options": ["Laporan Penerimaan TBS", "Rekap Penerimaan TBS"],
            "default": "Laporan Penerimaan TBS",
            "reqd": 1,
            "on_change": function() {
                let report = frappe.query_report;
                let laporan_type = report.get_filter_value('laporan');
                
                // Show/hide filters based on report type
                if (laporan_type === "Rekap Penerimaan TBS") {
                    report.get_filter('tbs').toggle(false);
                    report.get_filter('supplier').toggle(false);
                    report.get_filter('tanggal_dari').toggle(false);
                    report.get_filter('tanggal_sampai').toggle(false);
                    report.get_filter('company').toggle(true);
                    report.get_filter('tanggal').toggle(true);
                } else {
                    report.get_filter('tbs').toggle(true);
                    report.get_filter('supplier').toggle(true);
                    report.get_filter('tanggal_dari').toggle(true);
                    report.get_filter('tanggal_sampai').toggle(true);
                    report.get_filter('company').toggle(false);
                    report.get_filter('tanggal').toggle(false);
                }
                
                report.refresh();
            }
        },
        {
            "fieldname": "tbs",
            "label": __("TBS"),
            "fieldtype": "Select",
            "options": ["", "External", "Internal"],
            "default": "",
            "reqd": 0
        },
        {
            "fieldname": "supplier",
            "label": __("Supplier"),
            "fieldtype": "Link",
            "options": "Supplier",
            "reqd": 0,
            "get_query": function() {
                return {
                    "filters": {
                        "disabled": 0
                    }
                }
            }
        },
        {
            "fieldname": "tanggal_dari",
            "label": __("Tanggal Dari"),
            "fieldtype": "Date",
            "default": frappe.datetime.month_start(),
            "reqd": 0
        },
        {
            "fieldname": "tanggal_sampai",
            "label": __("Tanggal Sampai"),
            "fieldtype": "Date",
            "default": frappe.datetime.month_end(),
            "reqd": 0
        },
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "default": frappe.defaults.get_user_default("Company"),
            "reqd": 0,
            "hidden": 1
        },
        {
            "fieldname": "tanggal",
            "label": __("Tanggal"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 0,
            "hidden": 1
        }
    ],
    
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        
        let laporan_type = frappe.query_report.get_filter_value('laporan');
        
        if (laporan_type === "Rekap Penerimaan TBS") {
            // Format for Rekap report
            if (column.fieldname !== "driver_name") {
                if (value && !isNaN(parseFloat(value))) {
                    value = `<div style="text-align: right">${parseFloat(value).toLocaleString('id-ID', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>`;
                }
            }
            
            // Bold formatting for total rows
            if (data && (data.driver_name === "Total Internal" || data.driver_name === "Total External")) {
                value = `<div style="font-weight: bold">${value}</div>`;
            }
        } else {
            // Format for Laporan Penerimaan TBS
            if (column.fieldname == "bruto" || 
                column.fieldname == "tara" || 
                column.fieldname == "netto" ||
                column.fieldname == "potongan" ||
                column.fieldname == "berat_normal") {
                if (value && !isNaN(parseFloat(value))) {
                    value = `<div style="text-align: right">${parseFloat(value).toFixed(2)}</div>`;
                }
            }
        }
        
        return value;
    },
    
    "onload": function(report) {
        // Initialize filter visibility
        let laporan_type = report.get_filter_value('laporan');
        
        if (laporan_type === "Rekap Penerimaan TBS") {
            report.get_filter('tbs').toggle(false);
            report.get_filter('supplier').toggle(false);
            report.get_filter('tanggal_dari').toggle(false);
            report.get_filter('tanggal_sampai').toggle(false);
            report.get_filter('company').toggle(true);
            report.get_filter('tanggal').toggle(true);
        } else {
            report.get_filter('company').toggle(false);
            report.get_filter('tanggal').toggle(false);
        }
    }
};