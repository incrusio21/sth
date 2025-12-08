frappe.query_reports["Laporan Gaji Perawatan"] = {
	"filters": [
		{
			"fieldname": "bulan",
			"label": __("Bulan"),
			"fieldtype": "Select",
			"options": [
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
			"default": ""
		}
	]
};