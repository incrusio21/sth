# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from datetime import datetime
from dateutil.relativedelta import relativedelta

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = get_data()

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("bulan"):
		conditions += " AND DATE_FORMAT(dit.posting_date, '%%b') = %(bulan)s"

	return conditions

def get_data():
	data = frappe.db.sql("""
		SELECT
			ect.custom_pdo_type as jenis_kas,
			pkt.type as item_barang,
			pkt.needs as kebutuhan
		FROM `tabPermintaan Dana Operasional` pdo
		JOIN `tabPDO Kas Table` pkt ON pkt.parent = pdo.name
		JOIN `tabExpense Claim Type` ect ON ect.name = pkt.`type`
		WHERE pdo.name = 'PDO-00037'
		ORDER BY ect.custom_pdo_type, pkt.type
	""", as_dict=True)

	grouped_data = []
	current_group = None

	for row in data:
		# Header jenis kas
		if current_group != row.jenis_kas:
			grouped_data.append({
				"expenses": row.jenis_kas,
				"keterangan": "",
				"is_header": 1
			})

			# Sub header
			grouped_data.append({
				"expenses": "Item Barang",
				"keterangan": "Kebutuhan",
				"is_header": 1
			})

			current_group = row.jenis_kas

		# Detail item
		grouped_data.append({
			"expenses": f"   {row.item_barang}",
			"keterangan": row.kebutuhan,
			"is_header": 0
		})
	return grouped_data

def get_columns(filters):
	columns = [
		{
			"label": _("EXPENSES"),
			"fieldtype": "Data",
			"fieldname": "expenses",
		},
		{
			"label": _("KETERANGAN"),
			"fieldtype": "Data",
			"fieldname": "keterangan",
		},
	]

	# start = datetime.strptime(filters.from_date, "%Y-%m-%d")
	# end = datetime.strptime(filters.to_date, "%Y-%m-%d")

	# current = start

	# bulan_indo = [
	# 	"Januari", "Februari", "Maret", "April",
	# 	"Mei", "Juni", "Juli", "Agustus",
	# 	"September", "Oktober", "November", "Desember"
	# ]

	# while current <= end:
	# 	fieldname = current.strftime("%Y_%m")
	# 	bulan = bulan_indo[current.month - 1]
	# 	label = f"{bulan} {current.year}"

	# 	columns.append({
	# 		"label": f"Permintaan {label}",
	# 		"fieldtype": "Currency",
	# 		"fieldname": f"{fieldname}_permintaan",
	# 		"width": 200
	# 	})
	# 	columns.append({
	# 		"label": f"Realisasi {label}",
	# 		"fieldtype": "Currency",
	# 		"fieldname": f"{fieldname}_realisasi",
	# 		"width": 200
	# 	})
	# 	columns.append({
	# 		"label": f"Over/ Under Budget {label}",
	# 		"fieldtype": "Currency",
	# 		"fieldname": f"{fieldname}_selisih",
	# 		"width": 250
	# 	})

	# 	current += relativedelta(months=1)

	return columns