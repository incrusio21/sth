# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	query_l_equalisasi_pajak = frappe.db.sql(f"""
		SELECT
			pi.voucher_type as tipe_voucher,
			nvm.name as nvm,
			pi.name as pi_name,
			pi.supplier_name as nama_vendor,
			CASE 
				WHEN pi.voucher_type = "Voucher Match" 
				THEN pii.expense_account
				
				WHEN pi.voucher_type = "Non Voucher Match"
			THEN nvm.coa
				ELSE 0 
			END as kode_akun,
			CASE 
					WHEN pi.voucher_type = "Voucher Match" 
					THEN pi.total - pi.discount_amount
					
					WHEN pi.voucher_type = "Non Voucher Match"
				THEN nvm.dpp
					ELSE 0 
			END as dpp,
			CASE 
					WHEN pi.voucher_type = "Voucher Match" 
					THEN pi.total_pph_lainnya
					
					WHEN pi.voucher_type = "Non Voucher Match"
				THEN nvm.pph
					ELSE 0 
			END as pph,
			CASE 
					WHEN pi.voucher_type = "Voucher Match" 
					THEN pi.total_ppn
					
					WHEN pi.voucher_type = "Non Voucher Match"
				THEN nvm.ppn
					ELSE 0 
			END as ppn,
			pi.name as no_invoice,
			pi.no_fp as no_faktur,
			pi.no_faktur_pajak_pengganti as no_faktur_pengganti,
			pi.posting_date as tanggal_invoice,
			pi.total_pph_lainnya as summary_all_pph,
			pi.status as status
		FROM `tabPurchase Invoice` pi
		LEFT JOIN `tabPurchase Invoice Item` pii 
			ON pii.parent = pi.name
		LEFT JOIN `tabNon Voucher Match` nvm 
			ON nvm.parent = pi.name
			AND nvm.pph != 0
		WHERE pi.docstatus = 1
		{conditions}
	""", filters, as_dict=True)

	seen = set()

	for row in query_l_equalisasi_pajak:
			jenis_pajak = get_jenis_pajak(
					row.get("pi_name"),
					row.get("tipe_voucher"),
					row.get("nvm")
			)

			if not jenis_pajak:
					continue

			# filter by parent_tax_rate
			if filters.get("jenis_pajak"):
					parent_tax_rates = [
							d.get("parent_tax_rate")
							for d in jenis_pajak
							if d.get("parent_tax_rate")
					]

					if filters.get("jenis_pajak") not in parent_tax_rates:
							continue

			jenis_pajak_str = ", ".join([
					d["type"]
					for d in jenis_pajak
					if d.get("type")
			])

			# unique by invoice + jenis pajak
			unique_key = (
					row.get("no_invoice"),
					jenis_pajak_str
			)

			if unique_key in seen:
					continue

			seen.add(unique_key)

			row["jenis_pajak"] = jenis_pajak_str
			row["tanggal_bayar"] = get_oldest_payment_date(row.get("pi_name"))

			if row.get("tipe_voucher") == "Non Voucher Match":
				row["summary_all_pph"] = get_nvm_summary_all_pph(row.get("pi_name"))
   
			data.append(row)

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("company"):
		conditions += " AND pi.company = %(company)s"

	if filters.get("unit"):
		conditions += " AND pi.unit = %(unit)s"

	# if filters.get("jenis_pajak"):
	# 	conditions += """
	# 		AND (
	# 			%(jenis_pajak)s IS NULL
	# 			OR tr.parent_tax_rate = %(jenis_pajak)s
	# 		)
	# 	"""

	if filters.get("from_date") and filters.get("to_date"):
		conditions += " AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("Tanggal Bayar"),
			"fieldtype": "Date",
			"fieldname": "tanggal_bayar",
		},
		{
			"label": _("Nama Vendor"),
			"fieldtype": "Data",
			"fieldname": "nama_vendor",
		},
		{
			"label": _("Kode Akun"),
			"fieldtype": "Data",
			"fieldname": "kode_akun",
		},
		{
			"label": _("DPP"),
			"fieldtype": "Currency",
			"fieldname": "dpp",
		},
		{
			"label": _("PPH"),
			"fieldtype": "Currency",
			"fieldname": "pph",
		},
		{
			"label": _("PPN"),
			"fieldtype": "Currency",
			"fieldname": "ppn",
		},
		{
			"label": _("No Invoice"),
			"fieldtype": "Data",
			"fieldname": "no_invoice",
		},
		{
			"label": _("No Faktur"),
			"fieldtype": "Data",
			"fieldname": "no_faktur",
		},
		{
			"label": _("No Faktur Pengganti"),
			"fieldtype": "Data",
			"fieldname": "no_faktur_pengganti",
		},
		{
			"label": _("Tanggal Invoice"),
			"fieldtype": "Date",
			"fieldname": "tanggal_invoice",
		},
		{
			"label": _("Jenis Pajak"),
			"fieldtype": "Data",
			"fieldname": "jenis_pajak",
		},
		{
			"label": _("Summary All PPH"),
			"fieldtype": "Currency",
			"fieldname": "summary_all_pph",
		},
		{
			"label": _("Status"),
			"fieldtype": "Data",
			"fieldname": "status",
		},
	]

	return columns

def get_jenis_pajak(parent, tipe_voucher, nvm_name):
    query = []

    if tipe_voucher == "Voucher Match":
        query = frappe.db.sql("""
						SELECT
						vd.`type`,
						tr.parent_tax_rate
						FROM `tabVAT Detail` as vd
						JOIN `tabTax Rate` as tr ON tr.name = vd.`type`
            WHERE vd.parent = %(parent)s
        """, {
            "parent": parent
        }, as_dict=True)

    elif tipe_voucher == "Non Voucher Match":
        query = frappe.db.sql("""
            SELECT 
								nvm.pilih_pph as type,
								tr_pph.parent_tax_rate
						FROM `tabNon Voucher Match` nvm
						JOIN `tabTax Rate` tr_pph 
								ON tr_pph.name = nvm.pilih_pph
						WHERE nvm.name = %(nvm_name)s

						UNION ALL

						SELECT 
								nvm.pilih_ppn as type,
								tr_ppn.parent_tax_rate
						FROM `tabNon Voucher Match` nvm
						JOIN `tabTax Rate` tr_ppn 
								ON tr_ppn.name = nvm.pilih_ppn
						WHERE nvm.name = %(nvm_name)s;
        """, {
            "nvm_name": nvm_name
        }, as_dict=True)

    return query
  
def get_nvm_summary_all_pph(parent):
  query = frappe.db.sql("""
		SELECT 
				SUM(nvm.pph) as summary_all_pph
		FROM `tabNon Voucher Match` nvm
		JOIN `tabTax Rate` tr_ppn 
				ON tr_ppn.name = nvm.pilih_ppn
		WHERE nvm.parent = %(parent)s;
  """, {
		"parent": parent
	}, as_dict=True)
  
  return query[0].summary_all_pph or 0

def get_oldest_payment_date(parent):
  query = frappe.db.sql("""
		SELECT MIN(pe.posting_date) AS oldest_payment_date
		FROM `tabPayment Entry Reference` per
		INNER JOIN `tabPayment Entry` pe
				ON pe.name = per.parent
		WHERE per.reference_doctype = 'Purchase Invoice'
		AND per.reference_name = %(parent)s
		AND pe.docstatus = 1;
  """, {
		"parent": parent
	}, as_dict=True)
  
  return query[0].oldest_payment_date or 0