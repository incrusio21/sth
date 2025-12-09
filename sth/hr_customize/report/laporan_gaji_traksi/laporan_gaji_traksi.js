frappe.query_reports["Laporan Gaji Traksi"] = {
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
			"fieldname": "kendaraan",
			"label": __("Kendaraan"),
			"fieldtype": "Link",
			"options": "Alat Berat Dan Kendaraan",
			"default": ""
		}
	]
};