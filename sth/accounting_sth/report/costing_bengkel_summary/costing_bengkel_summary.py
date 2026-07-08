import frappe

# Mapping kode COA (prefix, dicocokkan dengan startswith) ke fieldname kolom report.
ACCOUNT_CODE_FIELD_MAP = {
	"4111001": "gaji_karyawan_bengkel",
	"4111002": "premi_lembur_bengkel",
	"4111003": "pemeliharaan_bengkel",
	"4111004": "pemakaian_barang_bengkel",
	"4111005": "alokasi_biaya_umum_bengkel",
	"4112001": "gaji_pengemudi",
	"4112002": "premi_lembur_kendaraan",
	"4112003": "bahan_bakar_pelumas",
	"4112004": "bahan_suku_cadang",
	"4112005": "reparasi_bengkel",
	"4112006": "reparasi_external",
	"4112007": "pajak_asuransi",
	"4112008": "penyusutan_kendaraan",
	"4112009": "alokasi_biaya_umum_kendaraan",
	"4112099": "biaya_kendaraan_dialokasi",
}


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	columns = [
		{"fieldname": "kode_kendaraan", "label": "Kode Kendaraan", "fieldtype": "Data", "width": 130},
		{"fieldname": "gaji_karyawan_bengkel", "label": "Gaji Karyawan Bengkel", "fieldtype": "Currency", "width": 150},
		{"fieldname": "premi_lembur_bengkel", "label": "Premi/Lembur", "fieldtype": "Currency", "width": 130},
		{"fieldname": "pemeliharaan_bengkel", "label": "Pemeliharaan Bengkel", "fieldtype": "Currency", "width": 150},
		{"fieldname": "pemakaian_barang_bengkel", "label": "Pemakaian Barang/Bahan Bengkel", "fieldtype": "Currency", "width": 200},
		{"fieldname": "alokasi_biaya_umum_bengkel", "label": "Alokasi Biaya Umum Dan Lain-lain", "fieldtype": "Currency", "width": 200},
		{"fieldname": "total_biaya_bengkel", "label": "Total Biaya Bengkel", "fieldtype": "Currency", "width": 150},
		{"fieldname": "gaji_pengemudi", "label": "Gaji Pengemudi", "fieldtype": "Currency", "width": 130},
		{"fieldname": "premi_lembur_kendaraan", "label": "Premi/Lembur", "fieldtype": "Currency", "width": 130},
		{"fieldname": "bahan_bakar_pelumas", "label": "Bahan Bakar Dan Pelumas", "fieldtype": "Currency", "width": 170},
		{"fieldname": "bahan_suku_cadang", "label": "Bahan Dan Suku Cadang", "fieldtype": "Currency", "width": 170},
		{"fieldname": "reparasi_bengkel", "label": "Reparasi Bengkel", "fieldtype": "Currency", "width": 140},
		{"fieldname": "reparasi_external", "label": "Reparasi External", "fieldtype": "Currency", "width": 140},
		{"fieldname": "pajak_asuransi", "label": "Pajak Dan Asuransi", "fieldtype": "Currency", "width": 140},
		{"fieldname": "penyusutan_kendaraan", "label": "Kendaraan - By. Penyusutan", "fieldtype": "Currency", "width": 170},
		{"fieldname": "alokasi_biaya_umum_kendaraan", "label": "Alokasi Biaya Umum Dan Lain-lain", "fieldtype": "Currency", "width": 200},
		{"fieldname": "biaya_kendaraan_dialokasi", "label": "Biaya Kendaraan Dialokasi", "fieldtype": "Currency", "width": 170},
		{"fieldname": "total_kmhm_vra", "label": "Total KM/HM VRA", "fieldtype": "Float", "precision": 2, "width": 140},
		{"fieldname": "total_cost_per_kmhm", "label": "Total Cost Per KM/HM", "fieldtype": "Currency", "width": 160},
	]
	return columns


def get_data(filters):
	conditions = []
	values = {}

	if filters.get("costing_bengkel"):
		conditions.append("cb.name = %(costing_bengkel)s")
		values["costing_bengkel"] = filters.get("costing_bengkel")

	if filters.get("company"):
		conditions.append("cb.company = %(company)s")
		values["company"] = filters.get("company")

	if filters.get("from_date"):
		conditions.append("cb.periode_dari >= %(from_date)s")
		values["from_date"] = filters.get("from_date")

	if filters.get("to_date"):
		conditions.append("cb.periode_sampai <= %(to_date)s")
		values["to_date"] = filters.get("to_date")

	condition_sql = ("AND " + " AND ".join(conditions)) if conditions else ""

	rows = frappe.db.sql("""
		SELECT t.kode_vra AS kode_vra, t.no_coa AS no_coa,
			SUM(t.debit) AS debit, SUM(t.credit) AS credit
		FROM (
			SELECT pb.kode_vra AS kode_vra, pb.no_coa AS no_coa, pb.amount AS debit, 0 AS credit
			FROM `tabCosting Bengkel Pengeluaran Barang` pb
			JOIN `tabCosting Bengkel` cb ON cb.name = pb.parent
			WHERE cb.docstatus != 2 {condition_sql}

			UNION ALL

			SELECT pbs.kode_vra, pbs.no_coa, pbs.amount, 0
			FROM `tabCosting Bengkel Pengeluaran Barang Solar` pbs
			JOIN `tabCosting Bengkel` cb ON cb.name = pbs.parent
			WHERE cb.docstatus != 2 {condition_sql}

			UNION ALL

			SELECT agk.kode_vra, agk.no_coa, agk.amount, 0
			FROM `tabCosting Bengkel Alokasi Gaji Karyawan Bengkel` agk
			JOIN `tabCosting Bengkel` cb ON cb.name = agk.parent
			WHERE cb.docstatus != 2 {condition_sql}

			UNION ALL

			SELECT ago.kode_vra, ago.no_coa, ago.amount, 0
			FROM `tabCosting Bengkel Alokasi Gaji Operator VRA` ago
			JOIN `tabCosting Bengkel` cb ON cb.name = ago.parent
			WHERE cb.docstatus != 2 {condition_sql}

			UNION ALL

			SELECT clb.kode_vra, clb.no_coa, clb.debit, clb.credit
			FROM `tabCosting Bengkel Closing Bengkel` clb
			JOIN `tabCosting Bengkel` cb ON cb.name = clb.parent
			WHERE cb.docstatus != 2 {condition_sql}

			UNION ALL

			SELECT glt.kode_vra, glt.no_coa, glt.debit, glt.credit
			FROM `tabCosting Bengkel GL BKM Traksi` glt
			JOIN `tabCosting Bengkel` cb ON cb.name = glt.parent
			WHERE cb.docstatus != 2 {condition_sql}

			UNION ALL

			SELECT clv.kode_vra, clv.no_coa, clv.debit, clv.credit
			FROM `tabCosting Bengkel Closing VRA` clv
			JOIN `tabCosting Bengkel` cb ON cb.name = clv.parent
			WHERE cb.docstatus != 2 {condition_sql}
		) t
		WHERE t.kode_vra IS NOT NULL AND t.kode_vra != ''
		GROUP BY t.kode_vra, t.no_coa
	""".format(condition_sql=condition_sql), values, as_dict=True)

	vehicles = {}

	def get_row(kode_vra):
		if kode_vra not in vehicles:
			row = {"kode_kendaraan": kode_vra, "total_biaya_bengkel": 0, "total_kmhm_vra": 0, "total_cost_per_kmhm": 0}
			row.update({field: 0 for field in ACCOUNT_CODE_FIELD_MAP.values()})
			vehicles[kode_vra] = row
		return vehicles[kode_vra]

	for r in rows:
		net = (r.debit or 0) - (r.credit or 0)
		row = get_row(r.kode_vra)
		account = r.no_coa or ""

		if account.startswith("411"):
			row["total_biaya_bengkel"] += net

		for code, fieldname in ACCOUNT_CODE_FIELD_MAP.items():
			if account.startswith(code):
				row[fieldname] += net
				break

	# Total KM/HM VRA — dari semua Buku Kerja Mandor Traksi yang submitted.
	# Jika filter costing_bengkel diisi, company & periode ikut dari dokumen tersebut.
	company = filters.get("company")
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")

	if filters.get("costing_bengkel"):
		cb_doc = frappe.db.get_value(
			"Costing Bengkel",
			filters.get("costing_bengkel"),
			["company", "periode_dari", "periode_sampai"],
			as_dict=True,
		)
		if cb_doc:
			company = company or cb_doc.company
			from_date = from_date or cb_doc.periode_dari
			to_date = to_date or cb_doc.periode_sampai

	kmhm_conditions = []
	kmhm_values = {}

	if company:
		kmhm_conditions.append("company = %(company)s")
		kmhm_values["company"] = company

	if from_date:
		kmhm_conditions.append("posting_date >= %(from_date)s")
		kmhm_values["from_date"] = from_date

	if to_date:
		kmhm_conditions.append("posting_date <= %(to_date)s")
		kmhm_values["to_date"] = to_date

	kmhm_condition_sql = ("AND " + " AND ".join(kmhm_conditions)) if kmhm_conditions else ""

	kmhm_rows = frappe.db.sql("""
		SELECT kendaraan, SUM(kmhm_akhir - kmhm_awal) AS total_kmhm
		FROM `tabBuku Kerja Mandor Traksi`
		WHERE docstatus = 1
			AND kendaraan IS NOT NULL
			AND kendaraan != ''
			{kmhm_condition_sql}
		GROUP BY kendaraan
	""".format(kmhm_condition_sql=kmhm_condition_sql), kmhm_values, as_dict=True)

	for r in kmhm_rows:
		row = get_row(r.kendaraan)
		row["total_kmhm_vra"] += r.total_kmhm or 0

	kmhm_bkl_rows = frappe.db.sql("""
		SELECT kd_kndr AS kendaraan, SUM(kmhm_akhir - kmhm_awal) AS total_kmhm
		FROM `tabBuku Kerja Mandor Bengkel`
		WHERE docstatus = 1
			AND kd_kndr IS NOT NULL
			AND kd_kndr != ''
			{kmhm_condition_sql}
		GROUP BY kd_kndr
	""".format(kmhm_condition_sql=kmhm_condition_sql), kmhm_values, as_dict=True)

	for r in kmhm_bkl_rows:
		row = get_row(r.kendaraan)
		row["total_kmhm_vra"] += r.total_kmhm or 0

	no_pol_map = {}
	if vehicles:
		no_pol_rows = frappe.db.get_all(
			"Alat Berat Dan Kendaraan",
			filters={"name": ["in", list(vehicles.keys())]},
			fields=["name", "no_pol"],
		)
		no_pol_map = {r.name: r.no_pol for r in no_pol_rows if r.no_pol}

	for kode_vra, row in vehicles.items():
		row["biaya_kendaraan_dialokasi"] = abs(row["biaya_kendaraan_dialokasi"])
		if row["total_kmhm_vra"]:
			row["total_cost_per_kmhm"] = row["biaya_kendaraan_dialokasi"] / row["total_kmhm_vra"]
		row["kode_kendaraan"] = no_pol_map.get(kode_vra, kode_vra)

	return sorted(vehicles.values(), key=lambda r: r["kode_kendaraan"] or "")
