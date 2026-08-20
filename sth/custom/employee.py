import frappe

def autoname_employee(self,method):
	self.finger_id = self.no_ktp[:14]
	self.name = self.no_ktp

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_stasiun_by_unit(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""
		SELECT
			sm.name,
			sm.machine_name
		FROM `tabDetail Station Master` dsm
		INNER JOIN `tabStation Master` sm
			ON sm.name = dsm.parent
		WHERE
			dsm.unit = %(unit)s
			AND sm.machine_name LIKE %(txt)s
		ORDER BY sm.machine_name
		LIMIT %(start)s, %(page_len)s
	""", {
		"unit": filters.get("unit"),
		"txt": f"%{txt}%",
		"start": start,
		"page_len": page_len,
	})

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_account_by_station_and_company(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""
		SELECT
			ca.name
		FROM `tabStation Procurement Settings` sps
		INNER JOIN `tabStation Master` sm
			ON sm.name = sps.parent
		INNER JOIN `tabAccount` a
			ON a.name = sps.account
		INNER JOIN `tabAccount` ca
			ON ca.parent_account = a.name
		WHERE
			sm.name = %(station)s
			AND sps.company = %(company)s
			AND ca.name LIKE '%%OPERASIONAL%%'
			AND ca.name LIKE %(txt)s
		ORDER BY ca.name
		LIMIT %(start)s, %(page_len)s
	""", {
		"station": filters.get("station"),
		"company": filters.get("company"),
		"txt": f"%{txt}%",
		"start": start,
		"page_len": page_len,
	})

@frappe.whitelist()
def get_coa_stasiun_options(station, company):
	"""Akun operasional milik satu stasiun untuk satu company.

	Rantainya sama dengan pencarian coa_stasiun di atas: akun anak dari account
	yang dipasang di Station Procurement Settings. Dipisah supaya bisa dipakai
	tanpa paging, baik oleh form (isi otomatis) maupun oleh validate.
	"""
	if not station or not company:
		return []

	return frappe.db.sql_list("""
		SELECT
			ca.name
		FROM `tabStation Procurement Settings` sps
		INNER JOIN `tabAccount` a
			ON a.name = sps.account
		INNER JOIN `tabAccount` ca
			ON ca.parent_account = a.name
		WHERE
			sps.parent = %(station)s
			AND sps.parenttype = 'Station Master'
			AND sps.company = %(company)s
		ORDER BY ca.name
	""", {
		"station": station,
		"company": company,
	})

def validasi_stasiun_mill(self, method=None):
	"""Karyawan mill yang masih aktif wajib punya stasiun.

	Costing Mill membebankan gaji ke stasiun karyawannya; kalau stasiun kosong
	karyawannya lolos dari alokasi tanpa pesan apa pun dan biayanya nyangkut di
	akun beban gaji. Karyawan non-aktif dilewati supaya data lama tetap bisa
	disunting.
	"""
	if self.get("status") != "Active" or not self.get("unit"):
		return

	if self.get("stasiun"):
		return

	if not frappe.db.get_value("Unit", self.unit, "mill"):
		return

	frappe.throw(
		"Stasiun wajib diisi untuk karyawan di unit mill {0}.".format(
			frappe.bold(self.unit)
		),
		title="Stasiun Belum Diisi",
	)


def set_coa_stasiun(self, method=None):
	"""Isi COA Stasiun sesuai stasiun dan company karyawan.

	Kalau akun operasionalnya cuma satu, langsung diisi. Kalau lebih dari satu,
	pilihan user dihormati selama masih cocok dengan stasiun/company sekarang.
	Dipasang di server supaya data dari import atau API ikut terisi.
	"""
	if not self.get("stasiun"):
		self.coa_stasiun = None
		return

	options = get_coa_stasiun_options(self.stasiun, self.company)

	if len(options) == 1:
		self.coa_stasiun = options[0]
	elif self.coa_stasiun not in options:
		self.coa_stasiun = None
