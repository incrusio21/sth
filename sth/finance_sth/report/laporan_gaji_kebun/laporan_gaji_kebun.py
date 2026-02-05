# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = get_data(conditions, filters)

	return columns, data

def get_data(conditions, filters):
	slips = frappe.db.sql("""
		SELECT
			ss.name AS slip,
			e.name as id_karyawan,
			e.employee_name as nama,
			e.bank_ac_no as no_rekening,
			e.divisi,
			d.designation_name AS jabatan,
   		COALESCE(SUM(ssll.principal_amount), 0) AS cicilan,
			ss.total_deduction + COALESCE(SUM(ssll.principal_amount), 0) AS pemotong,
			ss.net_pay AS gaji_bersih
		FROM `tabSalary Slip` ss
		INNER JOIN `tabEmployee` e ON e.name = ss.employee
		JOIN `tabDesignation` d ON d.name = e.designation
  	LEFT JOIN `tabSalary Slip Loan` ssll ON ssll.parent = ss.name
		WHERE ss.company IS NOT NULL {}
		GROUP BY
		ss.name,
		e.name,
		e.employee_name,
		e.bank_ac_no,
		e.divisi,
		d.designation_name,
		ss.total_deduction,
		ss.net_pay;
	""".format(conditions), filters, as_dict=True)

	details = frappe.db.sql("""
		SELECT parent, salary_component, amount
		FROM `tabSalary Detail`
	""", as_dict=True)

	lembur_map = frappe.db.sql("""
		SELECT
			employee,
			COALESCE(SUM(overtime_total), 0) AS total_jam_lembur
		FROM `tabLembur List`
		GROUP BY employee
	""", as_dict=True)

	GAJI_KOTOR_KEYS = {
		"gaji_pokok",
		"upah_panen",
		"upah_perawatan",
		"upah_traksi",
		"hkne",
		"lembur",
		"natura",
		"premi_brondolan",
		"premi_kehadiran",
		"premi_tutup_buku",
		"premi_angkut",
		"premi_supervisi",
		"incentif_hke_panen",
		"incentif_output",
		"subsidi_tambahan",
		"rapel",
	}

	detail_map = {}
	gaji_kotor_map = {}
	for d in details:
		detail_map.setdefault(d.parent, {})[frappe.scrub(d.salary_component)] = d.amount

		if frappe.scrub(d.salary_component) in GAJI_KOTOR_KEYS:
			gaji_kotor_map[d.parent] = gaji_kotor_map.get(d.parent, 0) + (d.amount or 0)
  
	lembur_map = {
		l.employee: l.total_jam_lembur
		for l in lembur_map
	}

	for i, s in enumerate(slips):
		s.update(detail_map.get(s.slip, {}))
		s["nomer_urut"] = (i + 1)
		s["gaji_kotor"] = gaji_kotor_map.get(s.slip, 0)
		s["total_jam_lembur"] = lembur_map.get(s.nik, 0)

	return slips

def get_condition(filters):
	conditions = ""

	if filters.get("company"):
		conditions += " AND e.company = %(company)s"
  
	if filters.get("unit"):
		conditions += " AND ss.unit = %(unit)s"

	if filters.get("divisi"):
		conditions += " AND e.divisi = %(divisi)s"

	if filters.get("designation"):
		conditions += " AND e.designation = %(designation)s"
  
	if filters.get("employee"):
		conditions += " AND e.name = %(employee)s"

	if filters.get("grade"):
		conditions += " AND e.grade = %(grade)s"
	
	if filters.get("employment_type"):
		conditions += " AND e.employment_type = %(employment_type)s"

	if filters.get("bulan"):
		conditions += " AND DATE_FORMAT(ss.posting_date, '%%b') = %(bulan)s"

	if filters.get("tahun"):
		conditions += " AND DATE_FORMAT(ss.posting_date, '%%Y') = %(tahun)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("NOMER URUT"),
			"fieldtype": "Data",
			"fieldname": "nomer_urut",
			"width": 130
		},
		{
			"label": _("ID KARYAWAN"),
			"fieldtype": "Data",
			"fieldname": "id_karyawan",
		},
		{
			"label": _("NAMA"),
			"fieldtype": "Data",
			"fieldname": "nama",
		},
		{
			"label": _("NO REKENING"),
			"fieldtype": "Data",
			"fieldname": "no_rekening",
		},
		{
			"label": _("DIVISI"),
			"fieldtype": "Data",
			"fieldname": "divisi",
		},
		{
			"label": _("JABATAN"),
			"fieldtype": "Data",
			"fieldname": "jabatan",
		},
	]

	# q_column_earning = frappe.db.sql("""
	# 	SELECT sc.name FROM `tabSalary Component` as sc WHERE sc.type = 'Earning' AND sc.disabled != 1 AND sc.name != 'HKnE';
  # """, as_dict=True)
	q_column_earning = [
		{"label": "GAJI POKOK", "key": "gaji_pokok"},
		{"label": "UPAH PANEN", "key": "upah_panen"},
		{"label": "UPAH PERAWATAN", "key": "upah_perawatan"},
		{"label": "UPAH TRAKSI", "key": "upah_traksi"},
		{"label": "HKNE", "key": "hkne"},
		{"label": "LEMBUR", "key": "lembur"},
		{"label": "NATURA", "key": "natura"},
		{"label": "PREMI BRONDOLAN", "key": "premi_brondolan"},
		{"label": "PREMI KEHADIRAN", "key": "premi_kehadiran"},
		{"label": "PREMI TUTUP BUKU", "key": "premi_tutup_buku"},
		{"label": "PREMI ANGKUT", "key": "premi_angkut"},
		{"label": "PREMI SUPERVISI", "key": "premi_supervisi"},
		{"label": "INCENTIF HKE PANEN", "key": "incentif_hke_panen"},
		{"label": "INCENTIF OUTPUT", "key": "incentif_output"},
		{"label": "Subsidi Tambahan", "key": "subsidi_tambahan"},
		{"label": "Rapel", "key": "rapel"},
		# {"label": "Lembur", "key": "lembur"},
		# {"label": "HKNe", "key": "hkne"},
		# {"label": "Premi Panen", "key": "premi_panen_kontanan"},
		# {"label": "Premi Kehadiran", "key": "premi_kehadiran"},
		# {"label": "Premi Brondolan", "key": "upah_brondolan"},
		# {"label": "Catu Beras", "key": "natura"},
		# {"label": "Premi", "key": "premi"},
		# {"label": "Premi Perawatan", "key": "premi_perawatan"},
		# {"label": "Premi Transport", "key": "premi_transport"},
		# {"label": "Premi bmtbs", "key": "premi_tbs"},
		# {"label": "Premi Angkut", "key": "premi_angkut"},
		# {"label": "Premi Pengawasan", "key": "premi_pengawas"},
	]
  
	# q_column_deduction = frappe.db.sql("""
	# 	SELECT sc.name FROM `tabSalary Component` as sc WHERE sc.type = 'Deduction' AND sc.disabled != 1;
  # """, as_dict=True)
	q_column_deduction = [
		{"label": "JHT 2%", "key": "bpjs_tk___jht_(karyawan)"},
		{"label": "JP 1%", "key": "bpjs_tk___jp_(karyawan)"},
		{"label": "BPJS KES 1%", "key": "bpjs_kesehatan_(karyawan)"},
		{"label": "PINALTI DENDA PANEN", "key": "denda_panen"},
		{"label": "POTONGAN KOPERASI", "key": "potongan_koperasi"},
		{"label": "POTONGAN SPSI", "key": "potongan_spsi"},
		{"label": "POTONGAN SBSI", "key": "potongan_sp_sbsi"},
		{"label": "POTONGAN KSBSI", "key": "potongan_ksbsi"},
		{"label": "POTONGAN SERBUK", "key": "potongan_serbuk"},
		{"label": "POTONGAN UANG SEKOLAH", "key": "potongan_uang_sekolah"},
		# {"label": "Potongan HK", "key": "potongan_hk"},
		# {"label": "BPJS Kesehatan (-)", "key": "bpjs_kesehatan_karyawan"},
		# {"label": "Potongan Basis HK", "key": "potongan_basis_hk"},
		# {"label": "BPJS JHT (-)", "key": "bpjs_tk_jht_karyawan"},
		# {"label": "Potongan Koperasi", "key": "potongan_koperasi"},
		# {"label": "Potongan Uang Sekolah", "key": "potongan_uang_sekolah"},
		# {"label": "BPJS Pensiun (-)", "key": "bpjs_pensiun"},
		# {"label": "Potongan SBSI", "key": "potongan_sp_sbsi"},
		# {"label": "Potongan SPSI", "key": "potongan_spsi"},
		# {"label": "Potongan HO", "key": "potongan_ho"},
		# {"label": "Potongan KSBSI", "key": "potongan_ksbsi"},
		# {"label": "Potongan Serbuk", "key": "potongan_serbuk"},
	]

	for earning in q_column_earning:
		# columns.append({
		# 	"label": earning.name,
		# 	"fieldtype": "Currency",
		# 	"fieldname": frappe.scrub(earning.name),
		#   "width": 150
		# })
		columns.append({
			"label": earning["label"],
			"fieldtype": "Currency",
			"fieldname": frappe.scrub(earning["key"]),
   		"width": 150
		})
  
	columns.append({
		"label": _("GAJI KOTOR"),
		"fieldtype": "Currency",
		"fieldname": "gaji_kotor",
	})

	for deduction in q_column_deduction:
		# columns.append({
		# 	"label": deduction.name,
		# 	"fieldtype": "Currency",
		# 	"fieldname": frappe.scrub(deduction.name),
		# 	"width": 150
		# })
		columns.append({
			"label": deduction["label"],
			"fieldtype": "Currency",
			"fieldname": frappe.scrub(deduction["key"]),
   		"width": 150
		})

	columns.append({
		"label": _("CICILAN"),
		"fieldtype": "Currency",
		"fieldname": "cicilan",
	})
 
	columns.append({
		"label": _("PEMOTONG"),
		"fieldtype": "Currency",
		"fieldname": "pemotong",
	})

	columns.append({
		"label": _("GAJI BERSIH"),
		"fieldtype": "Currency",
		"fieldname": "gaji_bersih",
	})

	return columns