import frappe
from frappe import _
from frappe.utils import getdate, formatdate

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	return [
		{
			"fieldname": "kode_kendaraan",
			"label": _("Kode Kendaraan"),
			"fieldtype": "Link",
			"options": "Alat Berat Dan Kendaraan",
			"width": 150
		},
		{
			"fieldname": "no_transaksi",
			"label": _("No Transaksi"),
			"fieldtype": "Link",
			"options": "Buku Kerja Mandor Traksi",
			"width": 150
		},
		{
			"fieldname": "tanggal",
			"label": _("Tanggal"),
			"fieldtype": "Data",
			"width": 100
		},
		{
			"fieldname": "kegiatan",
			"label": _("Kegiatan"),
			"fieldtype": "Data",
			"width": 400
		},
		{
			"fieldname": "hasil_kerja",
			"label": _("Hasil Kerja"),
			"fieldtype": "Float",
			"width": 100
		},
		{
			"fieldname": "satuan",
			"label": _("Satuan"),
			"fieldtype": "Data",
			"width": 80
		},
		{
			"fieldname": "rupiah_satuan",
			"label": _("Rupiah / Satuan"),
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"fieldname": "upah",
			"label": _("Upah"),
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"fieldname": "premi",
			"label": _("Premi"),
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"fieldname": "total_rp",
			"label": _("Total Rp"),
			"fieldtype": "Currency",
			"width": 120
		}
	]

def get_data(filters):
	conditions = get_conditions(filters)
	
	query = """
		SELECT 
			parent.name as no_transaksi,
			parent.kendaraan as kode_kendaraan,
			parent.posting_date as tanggal,
			parent.kegiatan as kegiatan,
			parent.kegiatan_account as kegiatan_account,
			bkmt.qty as hasil_kerja,
			bkmt.rate as rupiah_satuan,
			bkmt.amount as upah,
			bkmt.premi_amount as premi
		FROM 
			`tabDetail BKM Hasil Kerja Traksi` as bkmt
	 	JOIN 
			`tabBuku Kerja Mandor Traksi` as parent 
			ON bkmt.parent = parent.name
		WHERE 
			parent.docstatus = 1
			{conditions}
		ORDER BY 
			parent.kendaraan, parent.posting_date
	""".format(conditions=conditions)
	
	result = frappe.db.sql(query, filters, as_dict=1)
	
	data = []
	kendaraan_totals = {}
	
	for row in result:
		# Get UOM dari master Kegiatan
		try:
			kegiatan_doc = frappe.get_doc("Kegiatan", row.kegiatan)
			satuan = kegiatan_doc.uom
		except:
			satuan = ""
		
		# Format tanggal ke M/d/YYYY
		tanggal_formatted = formatdate(row.tanggal, "M/d/YYYY") if row.tanggal else ""
		
		# Hitung Total Rp
		total_rp = (row.upah or 0) + (row.premi or 0)
		
		# Tambahkan ke data
		data_row = {
			"kode_kendaraan": row.kode_kendaraan,
			"no_transaksi": row.no_transaksi,
			"tanggal": tanggal_formatted,
			"kegiatan": row.kegiatan_account,
			"hasil_kerja": row.hasil_kerja or 0,
			"satuan": satuan,
			"rupiah_satuan": row.rupiah_satuan or 0,
			"upah": row.upah or 0,
			"premi": row.premi or 0,
			"total_rp": total_rp
		}
		
		data.append(data_row)
		
		# Akumulasi total per kendaraan
		if row.kode_kendaraan not in kendaraan_totals:
			kendaraan_totals[row.kode_kendaraan] = {
				"upah": 0,
				"premi": 0,
				"total_rp": 0
			}
		
		kendaraan_totals[row.kode_kendaraan]["upah"] += row.upah or 0
		kendaraan_totals[row.kode_kendaraan]["premi"] += row.premi or 0
		kendaraan_totals[row.kode_kendaraan]["total_rp"] += total_rp
	
	# Tambahkan baris total per kendaraan
	final_data = []
	current_kendaraan = None
	
	for row in data:
		if current_kendaraan and current_kendaraan != row["kode_kendaraan"]:
			# Tambahkan total untuk kendaraan sebelumnya
			final_data.append({
				"kode_kendaraan": "",
				"no_transaksi": "",
				"tanggal": "",
				"kegiatan": f"<b>Total {current_kendaraan}</b>",
				"hasil_kerja": None,
				"satuan": "",
				"rupiah_satuan": None,
				"upah": kendaraan_totals[current_kendaraan]["upah"],
				"premi": kendaraan_totals[current_kendaraan]["premi"],
				"total_rp": kendaraan_totals[current_kendaraan]["total_rp"]
			})
		
		final_data.append(row)
		current_kendaraan = row["kode_kendaraan"]
	
	# Tambahkan total untuk kendaraan terakhir
	if current_kendaraan:
		final_data.append({
			"kode_kendaraan": "",
			"no_transaksi": "",
			"tanggal": "",
			"kegiatan": f"<b>Total {current_kendaraan}</b>",
			"hasil_kerja": None,
			"satuan": "",
			"rupiah_satuan": None,
			"upah": kendaraan_totals[current_kendaraan]["upah"],
			"premi": kendaraan_totals[current_kendaraan]["premi"],
			"total_rp": kendaraan_totals[current_kendaraan]["total_rp"]
		})
	
	return final_data

def get_conditions(filters):
	conditions = []
	
	if filters.get("bulan"):
		bulan_map = {
			"Januari": 1, "Februari": 2, "Maret": 3, "April": 4,
			"Mei": 5, "Juni": 6, "Juli": 7, "Agustus": 8,
			"September": 9, "Oktober": 10, "November": 11, "Desember": 12
		}
		month_num = bulan_map.get(filters.get("bulan"))
		if month_num:
			conditions.append(f"MONTH(parent.posting_date) = {month_num}")
	
	if filters.get("tahun"):
		conditions.append("YEAR(parent.posting_date) = %(tahun)s")
	
	if filters.get("kendaraan"):
		conditions.append("parent.kendaraan = %(kendaraan)s")
	
	return " AND " + " AND ".join(conditions) if conditions else ""