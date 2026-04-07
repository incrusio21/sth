// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Gaji Staff Up"] = {
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
			"fieldname": "bulan",
			"label": __("Bulan"),
			"fieldtype": "Select",
			"options": [
				"",
				"Januari",
				"Februari",
				"Maret",
				"April",
				"Mei",
				"Juni",
				"Juli",
				"Agustus",
				"September",
				"Oktober",
				"November",
				"Desember"
			],
			"default": ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"][new Date().getMonth()],
		},
		{
			"fieldname": "tahun",
			"label": __("Tahun"),
			"fieldtype": "Link",
			"options": "Fiscal Year",
			"default": new Date().getFullYear(),
		},
		{
			"fieldname": "employee",
			"label": __("Karyawan"),
			"fieldtype": "Link",
			"options": "Employee",
		}
	],
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		const targetFields = [
			"bpjs_kesehatan",
			"jht",
			"jp",
			"angsuran_motor",
			"potongan_lainnya",
			"deduction"
		];

		if (targetFields.includes(column.fieldname)) {
			value = `<span style="color:red; font-weight:bold">${value}</span>`;
		}

		return value;
	},
	onload: function (report) {
		setTimeout(() => {
			const targetHeaders = [
				"BPJS Kesehatan",
				"JHT",
				"JP",
				"Angsuran Motor",
				"Potongan Lainnya",
				"DEDUCTION"
			];

			$(".dt-header .dt-cell__content").each(function () {
				if (targetHeaders.includes($(this).text().trim())) {
					$(this).css({
						color: "red",
						fontWeight: "bold"
					});
				}
			});
		}, 500);
	}
};
