# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from datetime import datetime
from dateutil.relativedelta import relativedelta

def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("company"):
		conditions += " AND pdo.company = %(company)s"

	if filters.get("unit"):
		conditions += " AND pdo.unit = %(unit)s"

	if filters.get("year"):
		conditions += " AND pdo.fiscal_year = %(year)s"

	return conditions

def get_data(filters):
	conditions = get_condition(filters)

	data = frappe.db.sql("""
		SELECT
			pdo.name as pdo_name,
			pdo.posting_date,
			ect.custom_pdo_type as jenis_kas,
			pkt.type as item_barang,
			pkt.needs as kebutuhan,
			pkt.revised_total as permintaan,
			pkt.total as realisasi,
			pkt.revised_total - pkt.total as selisih
		FROM `tabPermintaan Dana Operasional` pdo
		JOIN `tabPDO Kas Table` pkt ON pkt.parent = pdo.name
		JOIN `tabExpense Claim Type` ect ON ect.name = pkt.`type`
		WHERE 1=1 {conditions}
		ORDER BY ect.custom_pdo_type, pkt.type
	""".format(conditions=conditions), filters, as_dict=True)

	months = get_month_range(filters)

	grouped = {}
	result = []
	current_group = None

	for row in data:
		# key unik per item
		key = (row.jenis_kas, row.item_barang, row.kebutuhan)

		if key not in grouped:
			grouped[key] = {
				"expenses": f"   {row.item_barang}",
				"keterangan": row.kebutuhan,
				"jenis_kas": row.jenis_kas,
			}

			# init semua bulan = 0
			for m in months:
				field = m.strftime("%Y_%m")
				grouped[key][f"{field}_permintaan"] = 0
				grouped[key][f"{field}_realisasi"] = 0
				grouped[key][f"{field}_selisih"] = 0

		# mapping ke bulan
		posting = row.posting_date
		field = posting.strftime("%Y_%m")

		grouped[key][f"{field}_permintaan"] += row.permintaan or 0
		grouped[key][f"{field}_realisasi"] += row.realisasi or 0
		grouped[key][f"{field}_selisih"] += row.selisih or 0

	# convert ke list + grouping header
	for key, val in grouped.items():
		if current_group != val["jenis_kas"]:
			result.append({
				"expenses": val["jenis_kas"],
				"keterangan": "",
				"is_header": 1
			})
			result.append({
				"expenses": "Item Barang",
				"keterangan": "Kebutuhan",
				"is_header": 1
			})
			current_group = val["jenis_kas"]

		result.append(val)

	return result

def get_month_range(filters):
	from datetime import datetime

	month_map = {
		"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
		"May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
		"Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
	}

	year = filters.get("year")
	from_month = filters.get("from_month")
	to_month = filters.get("to_month")

	# default: full year
	start_month = 1
	end_month = 12

	if from_month and to_month:
		start_month = month_map.get(from_month)
		end_month = month_map.get(to_month)

	months = []
	for m in range(start_month, end_month + 1):
		current = datetime(int(year), m, 1)
		months.append(current)

	return months

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
	bulan_indo = [
		"Januari", "Februari", "Maret", "April",
		"Mei", "Juni", "Juli", "Agustus",
		"September", "Oktober", "November", "Desember"
	]

	months = get_month_range(filters)

	for current in months:
		fieldname = current.strftime("%Y_%m")
		bulan = bulan_indo[current.month - 1]
		label = f"{bulan} {current.year}"

		columns.append({
			"label": f"Permintaan {label}",
			"fieldtype": "Currency",
			"fieldname": f"{fieldname}_permintaan",
			"width": 200
		})
		columns.append({
			"label": f"Realisasi {label}",
			"fieldtype": "Currency",
			"fieldname": f"{fieldname}_realisasi",
			"width": 200
		})
		columns.append({
			"label": f"Over/ Under Budget {label}",
			"fieldtype": "Currency",
			"fieldname": f"{fieldname}_selisih",
			"width": 250
		})

	return columns

# def get_columns(filters):
# 	columns = [
# 		{
# 			"label": _("EXPENSES"),
# 			"fieldtype": "Data",
# 			"fieldname": "expenses",
# 		},
# 		{
# 			"label": _("KETERANGAN"),
# 			"fieldtype": "Data",
# 			"fieldname": "keterangan",
# 		},
# 	]

# 	# start = datetime.strptime(filters.from_date, "%Y-%m-%d")
# 	# end = datetime.strptime(filters.to_date, "%Y-%m-%d")

# 	# current = start

# 	# bulan_indo = [
# 	# 	"Januari", "Februari", "Maret", "April",
# 	# 	"Mei", "Juni", "Juli", "Agustus",
# 	# 	"September", "Oktober", "November", "Desember"
# 	# ]

# 	# while current <= end:
# 	# 	fieldname = current.strftime("%Y_%m")
# 	# 	bulan = bulan_indo[current.month - 1]
# 	# 	label = f"{bulan} {current.year}"

# 	# 	columns.append({
# 	# 		"label": f"Permintaan {label}",
# 	# 		"fieldtype": "Currency",
# 	# 		"fieldname": f"{fieldname}_permintaan",
# 	# 		"width": 200
# 	# 	})
# 	# 	columns.append({
# 	# 		"label": f"Realisasi {label}",
# 	# 		"fieldtype": "Currency",
# 	# 		"fieldname": f"{fieldname}_realisasi",
# 	# 		"width": 200
# 	# 	})
# 	# 	columns.append({
# 	# 		"label": f"Over/ Under Budget {label}",
# 	# 		"fieldtype": "Currency",
# 	# 		"fieldname": f"{fieldname}_selisih",
# 	# 		"width": 250
# 	# 	})

# 	# 	current += relativedelta(months=1)

# 	return columns