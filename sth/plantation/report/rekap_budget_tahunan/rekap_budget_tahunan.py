# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import calendar

def execute(filters=None):
	columns = get_columns(filters)
	data = []
	all_months = {
    "jan": "per_januari",
    "feb": "per_februari",
    "mar": "per_maret",
    "apr": "per_april",
    "may": "per_mei",
    "jun": "per_juni",
    "jul": "per_juli",
    "aug": "per_agustus",
    "sep": "per_september",
    "oct": "per_oktober",
    "nov": "per_november",
    "dec": "per_desember"
	}

	# Sub-column bulanan
	for month in range(1, 13):
		columns.append({
			"label": calendar.month_abbr[month].upper(),  # JAN, FEB, ...
			"fieldname": calendar.month_abbr[month].lower(),
			"fieldtype": "Currency",
			"width": 150
		})

	# Tambahan kolom Rp/SAT
	columns.append({
		"label": "Rp/SAT",
		"fieldname": "rp_per_sat",
		"fieldtype": "Currency",
		"width": 120
	})

	# LAND CLEARING
	conditions_lc = get_condition(filters)
	query_lc = frappe.db.sql("""
	WITH base AS (
			SELECT 
					b.tahun_tanam,
					dbup.uom AS satuan,
					dbup.qty AS volume,
					bpt.grand_total,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_januari,0)/100))  AS jan,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_februari,0)/100)) AS feb,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_maret,0)/100))    AS mar,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_april,0)/100))    AS apr,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_mei,0)/100))      AS may,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_juni,0)/100))     AS jun,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_juli,0)/100))     AS jul,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_agustus,0)/100))  AS aug,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_september,0)/100))AS sep,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_oktober,0)/100))  AS oct,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_november,0)/100)) AS nov,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_desember,0)/100)) AS `dec`
			FROM `tabBudget Perawatan Tahunan` bpt
			JOIN `tabDetail Budget Upah Perawatan` dbup ON dbup.parent = bpt.name
			JOIN `tabBlok` b ON b.name = dbup.item
			WHERE bpt.kategori_kegiatan = "LC" {}
	),

	-- agregasi per tahun_tanam
	agg AS (
			SELECT
					tahun_tanam AS name,
					COUNT(*) AS jumlah_tahun_tanam,
					MAX(satuan) AS satuan,              -- diasumsikan sama per tahun
					SUM(volume) AS volume,
					SUM(grand_total) AS grand_total,
					SUM(jan) AS jan,
					SUM(feb) AS feb,
					SUM(mar) AS mar,
					SUM(apr) AS apr,
					SUM(may) AS may,
					SUM(jun) AS jun,
					SUM(jul) AS jul,
					SUM(aug) AS aug,
					SUM(sep) AS sep,
					SUM(oct) AS oct,
					SUM(nov) AS nov,
					SUM(`dec`) AS `dec`
			FROM base
			GROUP BY tahun_tanam
	),

	-- total semua tahun untuk normalisasi grand_total
	total AS (
			SELECT SUM(jumlah_tahun_tanam) AS total_tipe_tm
			FROM agg
	)

	SELECT
			a.name,
			a.jumlah_tahun_tanam,
			a.satuan,
			a.volume,
			(a.jumlah_tahun_tanam / t.total_tipe_tm) * a.grand_total AS grand_total,
			a.jan, a.feb, a.mar, a.apr, a.may, a.jun,
			a.jul, a.aug, a.sep, a.oct, a.nov, a.`dec`
	FROM agg a
	CROSS JOIN total t;
	""".format(conditions_lc), filters, as_dict=True)

	data.append({
		"uraian_kegiatan": "LAND CLEARING",
		"head": True
	})

	for idx, qlc in enumerate(query_lc):
		tm_row = {
			"uraian_kegiatan": f"{idx + 1}. TAHUN TANAM {qlc['name']} -> {qlc['jumlah_tahun_tanam']}",
			"satuan": qlc['satuan'],
			"volume": qlc['volume'],
			"amount": qlc['grand_total'],
			"rp_per_sat": qlc['grand_total'] / qlc['volume']
		}

		for key, month_field in all_months.items():
			tm_row[key] = qlc[key]

		data.append(tm_row)

	data.append({
		"uraian_kegiatan": "",
	})

	# BIBITAN
	conditions_bbt = get_condition(filters)
	query_bbt = frappe.db.sql("""
    SELECT 
    bpt.name,
    bpt.kategori_kegiatan,
    dbup.item AS batch,
    SUM(dbup.qty) AS volume,
    ROUND(COALESCE(bpt.grand_total,0)) AS grand_total,
    k.tp_bbt,
    k.uom,

    ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_januari,0)/100))  AS jan,
    ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_februari,0)/100)) AS feb,
    ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_maret,0)/100))    AS mar,
    ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_april,0)/100))    AS apr,
    ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_mei,0)/100))      AS may,
    ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_juni,0)/100))     AS jun,
    ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_juli,0)/100))     AS jul,
    ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_agustus,0)/100))  AS aug,
    ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_september,0)/100))AS sep,
    ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_oktober,0)/100))  AS oct,
    ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_november,0)/100)) AS nov,
    ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_desember,0)/100)) AS `dec`
    FROM `tabBudget Perawatan Tahunan` bpt
    JOIN `tabKegiatan` k ON k.name = bpt.kegiatan
    JOIN `tabDetail Budget Upah Pembibitan` dbup ON dbup.parent = bpt.name
    WHERE bpt.kategori_kegiatan = 'BBT' {}
    GROUP BY bpt.name;
	""".format(conditions_bbt), filters, as_dict=True)

	grouped = {}
	for row in query_bbt:
		key = row['tp_bbt']
		if key not in grouped:
			grouped[key] = []
		grouped[key].append(row)

	formated_bbt = []
	count_per_group = {k: len(v) for k, v in grouped.items()}
	total_tipe_bibitan = sum(count_per_group.values())

	for key, bbt in grouped.items():
		row_bbt = {
			"name": key,
			"jumlah_tipe_bbt": len(bbt),
			"satuan": bbt[0]['uom'],
			"volume": sum(b['volume'] for b in bbt),
			"amount": (len(bbt) / total_tipe_bibitan) * sum(b['grand_total'] for b in bbt),
		}

		for key, month_field in all_months.items():
			row_bbt[key] = sum(b[key] for b in bbt)
		
		formated_bbt.append(row_bbt)

	data.append({
		"uraian_kegiatan": "BIBITAN",
		"head": True
	})

	for idx, bbt in enumerate(formated_bbt):
		row_bbt = {
			"uraian_kegiatan": f"{idx + 1}. {bbt['name']} -> {bbt['jumlah_tipe_bbt']}",
			"satuan": bbt['satuan'],
			"volume": bbt['volume'],
			"amount": bbt['amount'],
			"rp_per_sat": bbt['amount'] / bbt['volume']
		}

		for key, month_field in all_months.items():
			row_bbt[key] = bbt[key]
	
		data.append(row_bbt)

	data.append({
		"uraian_kegiatan": "",
	})

	# PANEN
	conditions_pn = get_condition_panen(filters)
	query_pn = frappe.db.sql("""
	WITH base AS (
			SELECT 
					b.tahun_tanam,
					dbt.amount as volume,
					bpt.grand_total,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_januari,0)/100))  AS jan,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_februari,0)/100)) AS feb,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_maret,0)/100))    AS mar,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_april,0)/100))    AS apr,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_mei,0)/100))      AS may,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_juni,0)/100))     AS jun,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_juli,0)/100))     AS jul,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_agustus,0)/100))  AS aug,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_september,0)/100))AS sep,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_oktober,0)/100))  AS oct,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_november,0)/100)) AS nov,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_desember,0)/100)) AS `dec`
			FROM `tabBudget Panen Tahunan` as bpt
			JOIN `tabDetail Budget Tonase` as dbt ON dbt.parent = bpt.name
			JOIN `tabBlok` as b ON b.name = dbt.item
			WHERE stt = 'Aktif' {}
	),

	-- agregasi per tahun_tanam
	agg AS (
			SELECT
					tahun_tanam AS name,
					COUNT(*) AS jumlah_tahun_tanam,
					SUM(volume) AS volume,
					SUM(grand_total) AS grand_total,
					SUM(jan) AS jan,
					SUM(feb) AS feb,
					SUM(mar) AS mar,
					SUM(apr) AS apr,
					SUM(may) AS may,
					SUM(jun) AS jun,
					SUM(jul) AS jul,
					SUM(aug) AS aug,
					SUM(sep) AS sep,
					SUM(oct) AS oct,
					SUM(nov) AS nov,
					SUM(`dec`) AS `dec`
			FROM base
			GROUP BY tahun_tanam
	),

	-- total semua tahun untuk normalisasi grand_total
	total AS (
			SELECT SUM(jumlah_tahun_tanam) AS total_tipe_pn
			FROM agg
	)

	SELECT
			a.name,
			a.jumlah_tahun_tanam,
			(a.volume / 1000) as volume,
			(a.jumlah_tahun_tanam / t.total_tipe_pn) * a.grand_total AS grand_total,
			a.jan, a.feb, a.mar, a.apr, a.may, a.jun,
			a.jul, a.aug, a.sep, a.oct, a.nov, a.`dec`
	FROM agg a
	CROSS JOIN total t;
	""".format(conditions_pn), filters, as_dict=True)

	data.append({
		"uraian_kegiatan": "PANEN",
		"head": True
	})

	for idx, pn in enumerate(query_pn):
		tm_row = {
			"uraian_kegiatan": f"{idx + 1}. TAHUN TANAM {pn['name']} -> {pn['jumlah_tahun_tanam']}",
			"satuan": "TON",
			"volume": pn['volume'],
			"amount": pn['grand_total'],
			"rp_per_sat": pn['grand_total'] / pn['volume']
		}

		for key, month_field in all_months.items():
			tm_row[key] = pn[key]

		data.append(tm_row)

	data.append({
		"uraian_kegiatan": "",
	})

	# PERAWATAN TBM
	conditions_tbm = get_condition(filters)
	query_tbm = frappe.db.sql("""
	WITH base AS (
			SELECT 
					b.tahun_tanam,
					dbup.uom AS satuan,
					dbup.qty AS volume,
					bpt.grand_total,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_januari,0)/100))  AS jan,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_februari,0)/100)) AS feb,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_maret,0)/100))    AS mar,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_april,0)/100))    AS apr,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_mei,0)/100))      AS may,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_juni,0)/100))     AS jun,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_juli,0)/100))     AS jul,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_agustus,0)/100))  AS aug,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_september,0)/100))AS sep,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_oktober,0)/100))  AS oct,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_november,0)/100)) AS nov,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_desember,0)/100)) AS `dec`
			FROM `tabBudget Perawatan Tahunan` bpt
			JOIN `tabDetail Budget Upah Perawatan` dbup ON dbup.parent = bpt.name
			JOIN `tabBlok` b ON b.name = dbup.item
			WHERE bpt.kategori_kegiatan = "TBM" {}
	),

	-- agregasi per tahun_tanam
	agg AS (
			SELECT
					tahun_tanam AS name,
					COUNT(*) AS jumlah_tahun_tanam,
					MAX(satuan) AS satuan,              -- diasumsikan sama per tahun
					SUM(volume) AS volume,
					SUM(grand_total) AS grand_total,
					SUM(jan) AS jan,
					SUM(feb) AS feb,
					SUM(mar) AS mar,
					SUM(apr) AS apr,
					SUM(may) AS may,
					SUM(jun) AS jun,
					SUM(jul) AS jul,
					SUM(aug) AS aug,
					SUM(sep) AS sep,
					SUM(oct) AS oct,
					SUM(nov) AS nov,
					SUM(`dec`) AS `dec`
			FROM base
			GROUP BY tahun_tanam
	),

	-- total semua tahun untuk normalisasi grand_total
	total AS (
			SELECT SUM(jumlah_tahun_tanam) AS total_tipe_tm
			FROM agg
	)

	SELECT
			a.name,
			a.jumlah_tahun_tanam,
			a.satuan,
			a.volume,
			(a.jumlah_tahun_tanam / t.total_tipe_tm) * a.grand_total AS grand_total,
			a.jan, a.feb, a.mar, a.apr, a.may, a.jun,
			a.jul, a.aug, a.sep, a.oct, a.nov, a.`dec`
	FROM agg a
	CROSS JOIN total t;
	""".format(conditions_tbm), filters, as_dict=True)

	data.append({
		"uraian_kegiatan": "PERAWATAN TBM",
		"head": True
	})

	for idx, qtbm in enumerate(query_tbm):
		tm_row = {
			"uraian_kegiatan": f"{idx + 1}. TAHUN TANAM {qtbm['name']} -> {qtbm['jumlah_tahun_tanam']}",
			"satuan": qtbm['satuan'],
			"volume": qtbm['volume'],
			"amount": qtbm['grand_total'],
			"rp_per_sat": qtbm['grand_total'] / qtbm['volume']
		}

		for key, month_field in all_months.items():
			tm_row[key] = qtbm[key]

		data.append(tm_row)

	data.append({
		"uraian_kegiatan": "",
	})

	# PERAWATAN TM
	conditions_tm = get_condition(filters)
	query_tm = frappe.db.sql("""
	WITH base AS (
			SELECT 
					b.tahun_tanam,
					dbup.uom AS satuan,
					dbup.qty AS volume,
					bpt.grand_total,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_januari,0)/100))  AS jan,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_februari,0)/100)) AS feb,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_maret,0)/100))    AS mar,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_april,0)/100))    AS apr,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_mei,0)/100))      AS may,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_juni,0)/100))     AS jun,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_juli,0)/100))     AS jul,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_agustus,0)/100))  AS aug,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_september,0)/100))AS sep,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_oktober,0)/100))  AS oct,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_november,0)/100)) AS nov,
					ROUND(COALESCE(bpt.grand_total,0) * (COALESCE(bpt.per_desember,0)/100)) AS `dec`
			FROM `tabBudget Perawatan Tahunan` bpt
			JOIN `tabDetail Budget Upah Perawatan` dbup ON dbup.parent = bpt.name
			JOIN `tabBlok` b ON b.name = dbup.item
			WHERE bpt.kategori_kegiatan = "TM" {}
	),

	-- agregasi per tahun_tanam
	agg AS (
			SELECT
					tahun_tanam AS name,
					COUNT(*) AS jumlah_tahun_tanam,
					MAX(satuan) AS satuan,              -- diasumsikan sama per tahun
					SUM(volume) AS volume,
					SUM(grand_total) AS grand_total,
					SUM(jan) AS jan,
					SUM(feb) AS feb,
					SUM(mar) AS mar,
					SUM(apr) AS apr,
					SUM(may) AS may,
					SUM(jun) AS jun,
					SUM(jul) AS jul,
					SUM(aug) AS aug,
					SUM(sep) AS sep,
					SUM(oct) AS oct,
					SUM(nov) AS nov,
					SUM(`dec`) AS `dec`
			FROM base
			GROUP BY tahun_tanam
	),

	-- total semua tahun untuk normalisasi grand_total
	total AS (
			SELECT SUM(jumlah_tahun_tanam) AS total_tipe_tm
			FROM agg
	)

	SELECT
			a.name,
			a.jumlah_tahun_tanam,
			a.satuan,
			a.volume,
			(a.jumlah_tahun_tanam / t.total_tipe_tm) * a.grand_total AS grand_total,
			a.jan, a.feb, a.mar, a.apr, a.may, a.jun,
			a.jul, a.aug, a.sep, a.oct, a.nov, a.`dec`
	FROM agg a
	CROSS JOIN total t;
	""".format(conditions_tm), filters, as_dict=True)

	data.append({
		"uraian_kegiatan": "PERAWATAN TM",
		"head": True
	})

	for idx, qtm in enumerate(query_tm):
		tm_row = {
			"uraian_kegiatan": f"{idx + 1}. TAHUN TANAM {qtm['name']} -> {qtm['jumlah_tahun_tanam']}",
			"satuan": qtm['satuan'],
			"volume": qtm['volume'],
			"amount": qtm['grand_total'],
			"rp_per_sat": qtm['grand_total'] / qtm['volume']
		}

		for key, month_field in all_months.items():
			tm_row[key] = qtm[key]

		data.append(tm_row)

	data.append({
		"uraian_kegiatan": "",
	})

	# TRAKSI
	# query_trak = frappe.db.sql("""
	# 	SELECT btt.name, btt.grand_total, btt.total_km_hm, abdk.name as kode_kendaraan, abdk.uom
	# 	FROM `tabBudget Traksi Tahunan` as btt
	# 	JOIN `tabAlat Berat Dan Kendaraan` as abdk ON abdk.name = btt.kode_kendaraan
	# 	WHERE btt.company = 'PT Kalimantan Agung Lestari' AND btt.unit = 'TPRE' AND btt.thn_bgt = '2025';
	# """, as_dict=True)

	# data.append({
	# 	"uraian_kegiatan": "TRAKSI",
	# 	"head": True
	# })

	# for idx, trak in enumerate(query_trak):
	# 	# amount = int(trak['jumlah_tahun_tanam']) / int(sum_count_tahun_tanam) * int(trak['grand_total'])

	# 	data.append({
	# 		"uraian_kegiatan": f"{idx + 1}. {trak['kode_kendaraan']}",
	# 		"satuan": trak['uom'],
	# 		"volume": trak['total_km_hm'],
	# 		"amount": trak['grand_total']
	# 	})

	# data.append({
	# 	"uraian_kegiatan": "",
	# })

	# SUPERVISI
	# query_sup = frappe.db.sql("""
	# 	SELECT * FROM `tabBudget Supervisi Tahunan` 
	# 	WHERE company = 'PT Kalimantan Agung Lestari' AND unit = 'TPRE' AND thn_bgt = '2025';
	# """, as_dict=True)

	# sup_row = {
	# 	"uraian_kegiatan": "SUPERVISI",
	# 	"head": True,
	# 	"satuan": "Hari Kerja",
	# 	"amount": int(query_sup[0]['grand_total'])
	# }

	# for key, month_field in all_months.items():
	# 	sup_row[key] = calculate_percent(query_sup[0]['grand_total'], query_sup[0][month_field]) 

	# data.append(sup_row)

	# data.append({
	# 	"uraian_kegiatan": "",
	# })

	# BIAYA CAPITAL
	conditions_kap = get_condition_capital(filters)
	query_kap = frappe.db.sql("""
		SELECT bkt.grand_total FROM `tabBudget Kapital Tahunan` as bkt
		WHERE bkt.company IS NOT NULL {};
	""".format(conditions_kap), filters, as_dict=True)

	data.append({
		"uraian_kegiatan": "BIAYA CAPITAL",
		"head": True,
		"amount": int(query_kap[0]['grand_total']) if query_kap else 0
	})

	data.append({
		"uraian_kegiatan": "",
	})

	# BIAYA UMUM
	conditions_umum = get_condition_umum(filters)
	query_umm = frappe.db.sql("""
		SELECT * FROM `tabBudget Biaya Umum Tahunan` as bbut
		WHERE bbut.company IS NOT NULL {};
	""".format(conditions_umum), filters, as_dict=True)

	umm_row = {
		"uraian_kegiatan": "BIAYA UMUM",
		"head": True,
		"amount": int(query_umm[0]['grand_total']) if query_umm else 0
	}

	if query_umm:
		for key, month_field in all_months.items():
			umm_row[key] = calculate_percent(query_umm[0]['grand_total'], query_umm[0][month_field]) 

	data.append(umm_row)

	data.append({
		"uraian_kegiatan": "",
	})

	# GRAND TOTAL
	data.append({
		"uraian_kegiatan": "GRAND TOTAL",
		"head": True,
		"amount": sum(d.get("amount", 0) for d in data)
	})
	
	return columns, data

def calculate_percent(grand_total, percent):
	return int(grand_total) * (int(percent) / 100)

def get_condition(filters):
	conditions = "AND bpt.company = %(company)s"

	if filters.get("unit"):
		conditions += " AND bpt.unit = %(unit)s"
	
	if filters.get("divisi"):
		conditions += " AND bpt.divisi = %(divisi)s"
	
	if filters.get("kegiatan"):
		conditions += " AND bpt.kegiatan = %(kegiatan)s"
	
	if filters.get("periode"):
		conditions += " AND bpt.thn_bgt = %(periode)s"

	return conditions

def get_condition_panen(filters):
	conditions = "AND bpt.company = %(company)s"

	if filters.get("unit"):
		conditions += " AND bpt.unit = %(unit)s"
	
	if filters.get("divisi"):
		conditions += " AND bpt.divisi = %(divisi)s"
	
	if filters.get("periode"):
		conditions += " AND bpt.fiscal_year = %(periode)s"

	return conditions

def get_condition_capital(filters):
	conditions = "AND bkt.company = %(company)s"

	if filters.get("unit"):
		conditions += " AND bkt.unit = %(unit)s"
	
	if filters.get("periode"):
		conditions += " AND bkt.fiscal_year = %(periode)s"

	return conditions

def get_condition_umum(filters):
	conditions = "AND bbut.company = %(company)s"

	if filters.get("unit"):
		conditions += " AND bbut.unit = %(unit)s"
	
	if filters.get("periode"):
		conditions += " AND bbut.thn_bgt = %(periode)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("URAIAN KEGIATAN"),
			"fieldtype": "Data",
			"fieldname": "uraian_kegiatan",
			"width": 240,
		},
		{
			"label": _("SATUAN"),
			"fieldtype": "Data",
			"fieldname": "satuan",
			"width": 100,
		},
		{
			"label": _("VOLUME"),
			"fieldtype": "Data",
			"fieldname": "volume",
			"width": 120,
		},
		{
			"label": _("AMOUNT"),
			"fieldtype": "Currency",
			"fieldname": "amount",
			"width": 200,
		},
	]

	return columns