import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "label": _("No Transaksi"),
            "fieldname": "no_transaksi",
            "fieldtype": "Link",
            "options": "Attendance",
            "width": 200
        },
        {
            "label": _("Divisi"),
            "fieldname": "divisi",
            "fieldtype": "Data",
            "width": 150,
            "align": "left"
        },
        {
            "label": _("Nama Karyawan"),
            "fieldname": "nama_karyawan",
            "fieldtype": "Data",
            "width": 350
        },
        {
            "label": _("Tanggal"),
            "fieldname": "tanggal",
            "fieldtype": "Date",
            "width": 120
        },
        {
            "label": _("Kegiatan"),
            "fieldname": "kegiatan",
            "fieldtype": "Data",
            "width": 420
        },
        {
            "label": _("Absensi"),
            "fieldname": "absensi",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("Gaji Pokok"),
            "fieldname": "gaji_pokok",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Premi Kehadiran"),
            "fieldname": "premi_kehadiran",
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "label": _("Total"),
            "fieldname": "total",
            "fieldtype": "Currency",
            "width": 120
        }
    ]

def get_data(filters):
    conditions = get_conditions(filters)
    
    # Query utama untuk mendapatkan data attendance
    query = """
        SELECT 
            a.name as no_transaksi,
            e.custom_divisi as divisi,
            a.employee as employee_id,
            e.employee_name as nama_karyawan,
            a.attendance_date as tanggal,
            a.status as absensi,
            0 as gaji_pokok,
            0 as premi_kehadiran
        FROM 
            `tabAttendance` a
        LEFT JOIN 
            `tabEmployee` e ON a.employee = e.name
        WHERE 
            a.docstatus = 1
            {conditions}
        ORDER BY 
            e.employee_name, a.attendance_date
    """.format(conditions=conditions)
    
    attendance_data = frappe.db.sql(query, filters, as_dict=1)
    
    # Proses data dan kelompokkan per karyawan
    result = []
    employee_totals = {}
    
    for row in attendance_data:
        # Hitung total
        gaji_pokok = flt(row.gaji_pokok)
        premi_kehadiran = flt(row.premi_kehadiran)
        total = gaji_pokok + premi_kehadiran
        
        # Tambahkan ke result
        result.append({
            "no_transaksi": row.no_transaksi,
            "divisi": row.divisi or "",
            "nama_karyawan": row.nama_karyawan,
            "tanggal": row.tanggal,
            "kegiatan": "7111102-UPAH (NON-STAF) - KANTOR, UMUM DAN KEAMANAN",
            "absensi": row.absensi,
            "gaji_pokok": gaji_pokok,
            "premi_kehadiran": premi_kehadiran,
            "total": total
        })
        
        # Akumulasi total per karyawan
        employee_id = row.employee_id
        if employee_id not in employee_totals:
            employee_totals[employee_id] = {
                "nama_karyawan": row.nama_karyawan,
                "divisi": row.divisi or "",
                "gaji_pokok": 0,
                "premi_kehadiran": 0,
                "total": 0
            }
        
        employee_totals[employee_id]["gaji_pokok"] += gaji_pokok
        employee_totals[employee_id]["premi_kehadiran"] += premi_kehadiran
        employee_totals[employee_id]["total"] += total
    
    # Tambahkan baris total per karyawan
    final_result = []
    current_employee = None
    
    for row in result:
        if current_employee != row["nama_karyawan"]:
            # Jika ada karyawan sebelumnya, tambahkan total
            if current_employee:
                emp_data = next((v for k, v in employee_totals.items() 
                               if v["nama_karyawan"] == current_employee), None)
                if emp_data:
                    final_result.append({
                        "no_transaksi": "",
                        "divisi": "",
                        "nama_karyawan": f"<b>Total {current_employee}</b>",
                        "tanggal": "",
                        "kegiatan": "",
                        "absensi": "",
                        "gaji_pokok": emp_data["gaji_pokok"],
                        "premi_kehadiran": emp_data["premi_kehadiran"],
                        "total": emp_data["total"]
                    })
            current_employee = row["nama_karyawan"]
        
        final_result.append(row)
    
    # Tambahkan total untuk karyawan terakhir
    if current_employee:
        emp_data = next((v for k, v in employee_totals.items() 
                       if v["nama_karyawan"] == current_employee), None)
        if emp_data:
            final_result.append({
                "no_transaksi": "",
                "divisi": "",
                "nama_karyawan": f"<b>Total {current_employee}</b>",
                "tanggal": "",
                "kegiatan": "",
                "absensi": "",
                "gaji_pokok": emp_data["gaji_pokok"],
                "premi_kehadiran": emp_data["premi_kehadiran"],
                "total": emp_data["total"]
            })
    
    return final_result

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
			conditions.append(f"MONTH(a.attendance_date) = {month_num}")
	
	if filters.get("tahun"):
		conditions.append("YEAR(a.attendance_date) = %(tahun)s")
	
	if filters.get("employee"):
		conditions.append("a.employee = %(employee)s")
	
	return " AND " + " AND ".join(conditions) if conditions else ""