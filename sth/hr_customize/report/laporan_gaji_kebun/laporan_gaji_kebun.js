// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Gaji Kebun"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
		},
		{
			"fieldname": "unit",
			"label": __("Unit"),
			"fieldtype": "Link",
			"options": "Unit",
		},
		{
			"fieldname": "divisi",
			"label": __("Divisi"),
			"fieldtype": "Link",
			"options": "Divisi",
		},
		{
			"fieldname": "designation",
			"label": __("Jabatan"),
			"fieldtype": "Link",
			"options": "Designation",
		},
		{
			"fieldname": "grade",
			"label": __("Grade"),
			"fieldtype": "Link",
			"options": "Employee Grade",
		},
		{
			"fieldname": "employment_type",
			"label": __("Employment Type"),
			"fieldtype": "Link",
			"options": "Employment Type",
		},
		{
			"fieldname": "bulan",
			"label": __("Bulan"),
			"fieldtype": "Select",
			"options": [
				"",
				"Jan",
				"Feb",
				"Mar",
				"Apr",
				"May",
				"Jun",
				"Jul",
				"Aug",
				"Sep",
				"Oct",
				"Nov",
				"Dec"
			],
			"reqd": 1
		},
		{
			"fieldname": "tahun",
			"label": __("Tahun"),
			"fieldtype": "Link",
			"options": "Fiscal Year",
			"default": new Date().getFullYear(),
			"reqd": 1
		},
		{
			"fieldname": "employee",
			"label": __("Karyawan"),
			"fieldtype": "Link",
			"options": "Employee",
		}
	],
	// formatter: function (value, row, column, data, default_formatter) {
	// 	if (column.fieldname === "nomer_urut") {
	// 		return "";
	// 	}
	// 	return default_formatter(value, row, column, data);
	// },
	onload: function (report) {
		setTimeout(() => {
			const style = document.createElement("style");
			style.innerHTML = `
            .dt-cell--header-1,
            .dt-cell--col-1 {
                display: none !important;
            }
        `;
			document.head.appendChild(style);
			// document.querySelector(".dt-cell--header-1").style.display = "none";
			// document.querySelectorAll(".dt-cell--col-1").forEach(el => el.style.display = "none");

			// console.log(document.querySelectorAll(".dt-cell--col-1"));
		}, 1000);
	}
};
