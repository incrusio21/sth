import frappe
from frappe.utils import cint

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

def akun_stasiun(station, company):
	"""Akun yang boleh dipakai sebagai COA Stasiun untuk satu stasiun dan company.

	Akun yang dipasang di Station Procurement Settings lazimnya akun grup, dan
	yang dipakai karyawan adalah akun anaknya. Kalau akun itu sendiri sudah akun
	anak — BENGKEL misalnya, yang memakai 4111003 PEMELIHARAAN BENGKEL — dialah
	satu-satunya pilihan, tidak perlu dicarikan turunan yang memang tidak ada.

	Yang menentukan punya-tidaknya anak, bukan nama stasiunnya. Aturan lama
	memakai kata UMUM di nama stasiun dan menganggap stasiun itu tidak dipecah
	per kegiatan; nyatanya akunnya, 72110 BIAYA PEGAWAI STAF DAN NON-STAFF,
	punya lima belas anak. Akibatnya yang terpasang di karyawan justru akun grup
	itu sendiri, dan itu tidak akan pernah bisa dijurnal.

	Akun grup karena itu tidak pernah ikut hasil. GL Entry menolaknya mentah-
	mentah, jadi memasangnya di karyawan cuma menunda kegagalan sampai Costing
	Mill disubmit — sesudah Ambil Data terlihat normal dan tabel Closing tersusun.

	Ini satu-satunya sumber untuk dropdown maupun pengisian otomatis.
	set_coa_stasiun() mengosongkan coa_stasiun kalau nilainya tidak ada di
	daftar ini, jadi kalau dropdown-nya dibangun dari query yang berbeda,
	pilihan user akan terhapus sendiri tiap simpan.
	"""
	if not station or not company:
		return []

	terpasang = frappe.db.sql_list("""
		SELECT
			sps.account
		FROM `tabStation Procurement Settings` sps
		WHERE
			sps.parent = %(station)s
			AND sps.parenttype = 'Station Master'
			AND sps.company = %(company)s
			AND sps.account IS NOT NULL AND sps.account != ''
	""", {
		"station": station,
		"company": company,
	})

	if not terpasang:
		return []

	# Yang sudah berupa akun anak dipakai apa adanya; yang grup diganti anaknya.
	sendiri = frappe.get_all(
		"Account",
		filters={"name": ("in", terpasang), "is_group": 0},
		pluck="name",
	)
	anak = frappe.get_all(
		"Account",
		filters={"parent_account": ("in", terpasang), "is_group": 0},
		pluck="name",
	)

	return sorted(set(sendiri) | set(anak))

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_account_by_station_and_company(doctype, txt, searchfield, start, page_len, filters):
	"""Dropdown COA Stasiun.

	Disaring dan dipenggal di Python, bukan lewat SQL, supaya isinya dijamin
	sama persis dengan get_coa_stasiun_options(). Jumlah akun per stasiun
	sedikit, jadi tidak ada gunanya memaksakan paging di database.
	"""
	akun = akun_stasiun(filters.get("station"), filters.get("company"))

	if txt:
		akun = [nama for nama in akun if txt.lower() in nama.lower()]

	mulai = cint(start)

	return [[nama] for nama in akun[mulai:mulai + cint(page_len)]]

@frappe.whitelist()
def get_coa_stasiun_options(station, company):
	"""Akun COA Stasiun tanpa paging, untuk pengisian otomatis dan validate."""
	return akun_stasiun(station, company)

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

	Kalau akunnya cuma satu, langsung diisi. Kalau lebih dari satu,
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
