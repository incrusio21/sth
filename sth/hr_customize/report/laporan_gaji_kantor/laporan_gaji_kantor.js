frappe.query_reports["Laporan Gaji Kantor"] = {
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
			"fieldname": "unit",
			"label": __("Unit"),
			"fieldtype": "Link",
			"options": "Unit",
		},
		{
			"fieldname": "employment_type",
			"label": __("Tipe Karyawan"),
			"fieldtype": "Link",
			"options": "Employment Type",
		},
		{
			"fieldname": "divisi",
			"label": __("Divisi"),
			"fieldtype": "Link",
			"options": "Divisi",
		},
		{
			"fieldname": "employee",
			"label": __("Karyawan"),
			"fieldtype": "Link",
			"options": "Employee",
			"default": "",
			"get_query": function () {
				return {
					"filters": {
						"custom_kriteria": "Non Satuan Hasil"
					}
				};
			}
		}
	]
};