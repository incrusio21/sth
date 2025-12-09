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
	],
	
	"formatter": function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		
		if (data && data.kegiatan && data.kegiatan.includes("Total")) {
			if (column.fieldname === "upah" || column.fieldname === "premi" || column.fieldname === "total_rp") {
				value = value.bold();
			}
		}
		
		return value;
	}
};