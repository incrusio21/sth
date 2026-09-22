# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json

import frappe, erpnext
from frappe import _, _dict, scrub, unscrub

from frappe.model.document import Document

class DaftarBPJS(Document):

	def validate(self):
		current_employees = set()
		for row in self.daftar_bpjs_employee:
			if row.employee:
				current_employees.add(row.employee)
		
		rows_to_remove = []
		for idx, detail_row in enumerate(self.set_up_bpjs_detail_table):
			if detail_row.employee not in current_employees:
				rows_to_remove.append(idx)
		
		for idx in sorted(rows_to_remove, reverse=True):
			self.set_up_bpjs_detail_table.pop(idx)

		for idx, detail_row in enumerate(self.set_up_bpjs_detail_table):
			detail_row.idx = idx + 1
			
		self.set_missing_value()

	def set_missing_value(self):
		set_up_bpjs = frappe.get_cached_doc("Set Up BPJS PT", self.set_up_bpjs)
		detail_program = {d.nama_program: _dict({
			"salary_component_karyawan": d.salary_component_karyawan,
			"salary_component_perusahaan": d.salary_component_perusahaan,
			"expense_account": d.expense_account,
		}) for d in set_up_bpjs.set_up_bpjs_pt_table }

		for emp in self.set_up_bpjs_detail_table:
			if dp := detail_program.get(emp.program):
				emp.update(dp)

	def submit(self, auto_submit=False):
		if len(self.set_up_bpjs_detail_table) > 50:
			frappe.msgprint(
				_(
					"The task has been enqueued as a background job. In case there is any issue on processing in background, " \
					"the system will add a comment about the error on this Daftar BPJS and revert to the Draft stage"
				)
			)
			self.queue_action("submit", timeout=4600)
		else:
			self._submit()

	def before_submit(self):
		self.validate_komponen_lengkap()

	def validate_komponen_lengkap(self):
		"""Tolak submit kalau ada beban yang belum punya salary component.

		create_payment_log() hanya membuat log untuk beban yang tidak nol, jadi
		yang diperiksa persis pasangan itu. Tanpa penjagaan ini lognya lahir
		dengan salary_component kosong dan baru ketahuan waktu salary slip.

		Komponen yang kosong sebelah itu wajar — JKK dan JKM ditanggung penuh
		perusahaan, jadi sisi karyawannya memang tidak dipakai. Yang tidak wajar
		cuma kalau bebannya ada tapi komponennya tidak.
		"""
		kurang = set()

		for emp in self.set_up_bpjs_detail_table:
			for c_type in ("karyawan", "perusahaan"):
				if emp.get(f"beban_{c_type}") and not emp.get(f"salary_component_{c_type}"):
					kurang.add((emp.program, c_type))

		if not kurang:
			return

		daftar = ", ".join(
			f"{program} ({unscrub(c_type)})" for program, c_type in sorted(kurang)
		)
		frappe.throw(
			_(
				"Salary Component belum diisi untuk: {0}. Lengkapi dulu di Set Up BPJS PT "
				"<b>{1}</b>, lalu simpan ulang daftar ini."
			).format(daftar, self.set_up_bpjs),
			title=_("Salary Component Belum Lengkap"),
		)

	def on_submit(self):
		self.create_bpjs_document()
		self.create_payment_log()
	
	def create_bpjs_document(self):
		account = frappe.get_cached_value(
			"Company", self.pt, [
				"default_bpjs_tk_credit_account", 
				"default_bpjs_kes_credit_account",
			], as_dict=True
		)

		new_doc = frappe.new_doc(self.jenis_bpjs)
		new_doc.credit_to = account.get(f"default_{scrub(self.jenis_bpjs)}_credit_account")

		grand_total = 0
		for row in self.daftar_bpjs_employee:
			grand_total += row.jumlah

		new_doc.no_daftar_bpjs = self.name
		new_doc.grand_total = grand_total
		new_doc.outstanding_amount = 0
		new_doc.posting_date = self.end_periode
		new_doc.no_rekening_tujuan = self.no_rekening_tujuan

		new_doc.company = self.pt

		program_dict = {}
		for emp in self.set_up_bpjs_detail_table:
			program_dict.setdefault(emp.program, {
				"expense_account": emp.expense_account,
				"beban_karyawan": 0,
				"beban_perusahaan": 0,
				"total": 0
			})

			program_dict[emp.program]["beban_karyawan"] += emp.beban_karyawan
			program_dict[emp.program]["beban_perusahaan"] += emp.beban_perusahaan
			program_dict[emp.program]["total"] += emp.beban_karyawan + emp.beban_perusahaan

		new_doc.expense_total = json.dumps(program_dict)

		new_doc.save()
		new_doc.submit()

	def create_payment_log(self):

		for emp in self.set_up_bpjs_detail_table:
			for c_type in ["karyawan", "perusahaan"]:
				amount = emp.get(f"beban_{c_type}") or 0
				if amount:
					doc = frappe.new_doc("Employee Payment Log")
					doc.employee = emp.employee
					doc.company = self.pt
					doc.posting_date = self.start_periode
					doc.payroll_date = self.start_periode

					doc.amount = amount
					doc.salary_component = emp.get(f"salary_component_{c_type}")

					doc.voucher_type = self.doctype
					doc.voucher_no = self.name
					doc.voucher_detail_no = emp.name
					doc.component_type = f"BPJS {unscrub(c_type)}"

					doc.save()

	def on_cancel(self):
		self.remove_employee_payment_log()

	def remove_employee_payment_log(self):
		for epl in frappe.get_all(
			"Employee Payment Log", 
			filters={"voucher_type": self.doctype, "voucher_no": self.name}, 
			pluck="name"
		):
			frappe.delete_doc("Employee Payment Log", epl, flags=frappe._dict(transaction_employee=True))

	@frappe.whitelist()
	def get_employee(self):
		pasang_bpjs(self)

def debug_bpjs():
	doc = frappe.get_doc("Daftar BPJS","BPJS TK-PT. TRIMITRA LESTARI-02477")
	pasang_bpjs(doc)

# Indeks kolom hasil query di pasang_bpjs. Query-nya mengembalikan tuple, bukan
# dict, jadi urutan select di sana dan angka-angka di sini harus bergerak bersama.
KOLOM_EMPLOYEE = 0
KOLOM_SSA_FROM_DATE = 13
KOLOM_SSA_CREATION = 14


def ssa_terakhir_per_employee(rows):
	"""Sisakan satu baris per karyawan: Salary Structure Assignment terakhirnya.

	Query di pasang_bpjs berangkat dari Salary Structure Assignment, jadi hasilnya
	satu baris per SSA — bukan per karyawan. Karyawan yang SSA-nya pernah di-amend,
	atau yang upahnya pernah naik lewat SSA baru, punya lebih dari satu SSA yang
	from_date-nya masuk periode, dan dulu semuanya ikut terdaftar.

	Akibatnya bukan cuma dobel di daftar: create_payment_log membuat satu Employee
	Payment Log per baris set_up_bpjs_detail_table, dan slip membaca dari sana —
	jadi satu karyawan tertagih dua kali.

	Yang menang from_date terbesar; kalau seri, yang dibuat belakangan. Fungsi
	murni supaya bisa dites tanpa database.
	"""
	terpilih = {}

	for row in rows:
		employee = row[KOLOM_EMPLOYEE]
		lama = terpilih.get(employee)

		if lama is None or _kunci_ssa(row) > _kunci_ssa(lama):
			terpilih[employee] = row

	return list(terpilih.values())


def _kunci_ssa(row):
	"""Kunci urut satu baris SSA: tanggal berlaku, lalu waktu pembuatan."""
	return (
		frappe.utils.getdate(row[KOLOM_SSA_FROM_DATE]),
		row[KOLOM_SSA_CREATION],
	)


def pasang_bpjs(doc):
	# doc = frappe.get_doc("Daftar BPJS","BPJS TK-PT. TRIMITRA LESTARI-00162")

	Employee = frappe.qb.DocType("Employee")
	SSAssignment = frappe.qb.DocType("Salary Structure Assignment")
	query = (
			frappe.qb.from_(SSAssignment)
			.inner_join(Employee)
			.on(Employee.name == SSAssignment.employee)
			.select(
				SSAssignment.employee, 

				SSAssignment.base, 
				Employee.employee_name,
				Employee.no_ktp,
				Employee.designation,
				Employee.custom_no_bpjs_kesehatan if doc.jenis_bpjs != "BPJS TK" else Employee.custom_no_bpjs_ketenagakerjaan,
				
				Employee.custom_nama_ibu_kandung,
				Employee.blood_group,
				Employee.kelas_bpjs_kesehatan,
				SSAssignment.custom_tunjangan_komunikasi + SSAssignment.custom_tunjangan_daerah + SSAssignment.custom_tunjangan_perumahan,
				Employee.grade,

				Employee.custom_kriteria,
				Employee.jabatan,

				# dua kolom terakhir cuma dipakai ssa_terakhir_per_employee untuk
				# memilih baris, tidak ikut masuk tabel mana pun
				SSAssignment.from_date,
				SSAssignment.creation
				
				)
			.where(
				(Employee.unit == doc.unit)
				& (Employee.company == doc.pt)
				& (Employee.status == "Active")
				& (Employee.grade == "NON STAFF" if doc.golongan == "Non Staf" else Employee.grade != "NON STAFF" )
				& (SSAssignment.docstatus == 1)
				& (SSAssignment.from_date <= doc.start_periode)
			)
		)

	print(query)
	list_employee = ssa_terakhir_per_employee(query.run())
		
	list_program_employee = {}
	susunan_bpjs = frappe.get_doc("Set Up BPJS PT", doc.set_up_bpjs)
	for satu_employee in list_employee:
		list_program_employee[satu_employee[0]] = []
		for row in susunan_bpjs.set_up_bpjs_pt_table:
			program_doc = frappe.get_doc("Program BPJS", row.nama_program)
			batas = 0
			for baris_program in program_doc.program_bpjs_staff:
				if baris_program.golongan == "Non Staff" and satu_employee[10] == "NON STAFF":
					if baris_program.kriteria == "Satuan Hasil" and satu_employee[11] == "Satuan Hasil":
						batas = frappe.utils.flt(baris_program.batas_maksimum)
					elif baris_program.kriteria == "Non Satuan Hasil" and satu_employee[11] == "Non Satuan Hasil":
						batas = frappe.utils.flt(baris_program.batas_maksimum)

				elif baris_program.golongan == "Staf Up" and satu_employee[10] == "STAFF":
					if baris_program.kriteria == "Satuan Hasil" and satu_employee[11] == "Satuan Hasil":
						batas = frappe.utils.flt(baris_program.batas_maksimum)
					elif baris_program.kriteria == "Non Satuan Hasil" and satu_employee[11] == "Non Satuan Hasil":
						batas = frappe.utils.flt(baris_program.batas_maksimum)



			gp_satu = satu_employee[1]
			# if satu_employee[10] != "NON STAF":
			# 	gp_satu = satu_employee[1] + satu_employee[9]

			if batas > 0:
				if gp_satu > batas:
					gp_satu = batas

			list_program_employee[satu_employee[0]].append({
				"program" : row.nama_program,
				"beban_karyawan": row.beban_karyawan / 100 * gp_satu,
				"beban_perusahaan": row.beban_perusahaan / 100 * gp_satu
			})
	print(list_program_employee)

	doc.set_up_bpjs_detail_table = []
	doc.daftar_bpjs_employee = []

	for row in list_employee:
		gp_satu = row[1]
		# if row[10] != "NON STAF":
		# 	gp_satu = row[1] + row[9]

		satu_employee = row[0]
		gp = gp_satu
		nama_employee = row[2]
		no_ktp = row[3]
		jabatan = row[4]
		no_bpjs = row[5]
		nama_ibu = row[6]
		gol_darah = row[7]
		kelas_bpjs_kesehatan = row[8]
		nama_jabatan = row[12]
		beban_karyawan = 0
		beban_perusahaan = 0
		# masukkan semua detil ke table detail
		for satu_beban in list_program_employee[satu_employee]:
			if doc.jenis_bpjs == "BPJS KES":
				cek_kes = 0
				# perlu cek kelas nya
				if satu_beban.get("program") == kelas_bpjs_kesehatan:
					cek_kes = 1

				if cek_kes == 1:
					satu_row = doc.append("set_up_bpjs_detail_table")
				
					satu_row.employee = satu_employee

					satu_row.nama_employee = nama_employee
					satu_row.program = satu_beban.get("program")
					satu_row.beban_karyawan = satu_beban.get("beban_karyawan")
					satu_row.beban_perusahaan = satu_beban.get("beban_perusahaan")
					satu_row.nama_employee = nama_employee

					beban_karyawan += frappe.utils.flt(satu_row.beban_karyawan)
					beban_perusahaan += frappe.utils.flt(satu_row.beban_perusahaan)

			else:
				satu_row = doc.append("set_up_bpjs_detail_table")
				
				satu_row.employee = satu_employee
				satu_row.nama_employee = nama_employee
				satu_row.program = satu_beban.get("program")
				satu_row.beban_karyawan = satu_beban.get("beban_karyawan")
				satu_row.beban_perusahaan = satu_beban.get("beban_perusahaan")

				beban_karyawan += frappe.utils.flt(satu_row.beban_karyawan)
				beban_perusahaan += frappe.utils.flt(satu_row.beban_perusahaan)


		# masuk ke daftar bpjs employee
		satu_row_employee = doc.append("daftar_bpjs_employee")
		satu_row_employee.employee = satu_employee
		satu_row_employee.nama = nama_employee
		satu_row_employee.gp = gp_satu
		satu_row_employee.beban_karyawan = beban_karyawan
		satu_row_employee.beban_perusahaan = beban_perusahaan
		satu_row_employee.jumlah = beban_perusahaan + beban_karyawan

		satu_row_employee.no_ktp = no_ktp
		satu_row_employee.jabatan = jabatan
		satu_row_employee.no_bpjs_tkkes = no_bpjs
		satu_row_employee.nama_ibu_kandung = nama_ibu
		satu_row_employee.gol_darah = gol_darah

		satu_row_employee.nama_jabatan = nama_jabatan


# ---------------------------------------------------------------------------
# Penyelarasan ke master
# ---------------------------------------------------------------------------

# Kolom di Set Up BPJS Detail Table yang isinya salinan dari Set Up BPJS PT.
KOLOM_IKUT_MASTER = (
	"salary_component_karyawan",
	"salary_component_perusahaan",
	"expense_account",
)


def komponen_master(set_up_bpjs):
	"""Peta program -> komponen dan akun menurut Set Up BPJS PT sekarang."""
	rows = frappe.get_all(
		"Set Up BPJS PT Table",
		filters={"parent": set_up_bpjs, "parenttype": "Set Up BPJS PT"},
		fields=["nama_program", *KOLOM_IKUT_MASTER],
	)

	return {row.nama_program: row for row in rows}


def samakan_komponen_dengan_master(set_up_bpjs=None):
	"""Samakan komponen dan akun BPJS yang sudah dibekukan dengan masternya.

	set_missing_value() menyalin komponen dari Set Up BPJS PT waktu Daftar BPJS
	divalidasi, lalu create_payment_log() membekukan salinan itu ke Employee
	Payment Log waktu disubmit. Salary slip membacanya dari sana, sering
	berbulan-bulan kemudian. Kalau masternya dibetulkan di antara kedua saat itu,
	tidak ada yang menjalarkan perbaikannya: dokumen tersubmit tidak pernah
	divalidasi lagi. Juni 2026 di TPRE 674 baris kena begitu — komponen beban
	perusahaannya tetap versi Staff HO/RO, yang akunnya beban umum, padahal
	masternya sudah dibetulkan ke Opr Kebun yang masuk gaji dialokasi kebun.

	Yang disentuh cuma nama komponen dan akunnya, tidak pernah nilainya. Baris
	yang sudah dipakai salary slip tersubmit (`is_paid`) dilewati dan dilaporkan,
	karena mengubahnya berarti GL-nya tidak lagi cocok dengan slipnya.

	Aman diulang: yang sudah sama tidak disentuh.

	Balikan dict: detail, log, log_terkunci, slip_draft.

	`slip_draft` berisi (nama slip, komponen lama, komponen baru) — barisnya
	diganti namanya di tempat, slipnya jangan disimpan ulang. Penyimpanan ulang
	menambah baris komponen baru tanpa membuang yang lama, karena
	update_component_row() mencari baris lewat nama komponen dan yang lama tidak
	dicari siapa-siapa lagi. Uji coba 21 September 2026: gross ke-17 slip naik
	persis sebesar komponennya, dobel.
	"""
	syarat = {"docstatus": 1}
	if set_up_bpjs:
		syarat["set_up_bpjs"] = set_up_bpjs

	hasil = {"detail": 0, "log": 0, "log_terkunci": [], "slip_draft": set()}

	for daftar in frappe.get_all("Daftar BPJS", filters=syarat, fields=["name", "set_up_bpjs"]):
		master = komponen_master(daftar.set_up_bpjs)
		if not master:
			continue

		baris = frappe.get_all(
			"Set Up BPJS Detail Table",
			filters={"parent": daftar.name, "parenttype": "Daftar BPJS"},
			fields=["name", "program", "beban_karyawan", "beban_perusahaan", *KOLOM_IKUT_MASTER],
		)

		for det in baris:
			benar = master.get(det.program)
			if not benar:
				continue

			beda = {
				kolom: benar[kolom]
				for kolom in KOLOM_IKUT_MASTER
				if (det[kolom] or None) != (benar[kolom] or None)
			}
			if not beda:
				continue

			frappe.db.set_value("Set Up BPJS Detail Table", det.name, beda)
			hasil["detail"] += 1

			for c_type in ("karyawan", "perusahaan"):
				kolom = f"salary_component_{c_type}"
				if kolom in beda:
					perbaiki_payment_log(daftar.name, det.name, c_type, beda[kolom], hasil)

	return hasil


def perbaiki_payment_log(daftar_bpjs, voucher_detail_no, c_type, komponen_benar, hasil):
	"""Tulis komponen yang benar ke Employee Payment Log satu baris detail.

	Lognya dicari lewat voucher_detail_no dan component_type, dua kolom yang
	diisi create_payment_log() sendiri — bukan lewat nama komponen lamanya,
	supaya baris yang sempat diperbaiki manual tetap ketemu.
	"""
	logs = frappe.get_all(
		"Employee Payment Log",
		filters={
			"voucher_type": "Daftar BPJS",
			"voucher_no": daftar_bpjs,
			"voucher_detail_no": voucher_detail_no,
			"component_type": f"BPJS {unscrub(c_type)}",
		},
		fields=["name", "employee", "payroll_date", "salary_component", "is_paid"],
	)

	for log in logs:
		if log.salary_component == komponen_benar:
			continue

		if log.is_paid:
			hasil["log_terkunci"].append(f"{log.name} ({log.salary_component})")
			continue

		frappe.db.set_value("Employee Payment Log", log.name, "salary_component", komponen_benar)
		hasil["log"] += 1

		if not log.salary_component:
			continue

		# Slip draft yang memuat periode log ini sudah telanjur menyalin komponen
		# lamanya ke barisnya sendiri.
		hasil["slip_draft"].update(
			(slip, log.salary_component, komponen_benar)
			for slip in frappe.get_all(
				"Salary Slip",
				filters={
					"employee": log.employee,
					"docstatus": 0,
					"start_date": ("<=", log.payroll_date),
					"end_date": (">=", log.payroll_date),
				},
				pluck="name",
			)
		)
