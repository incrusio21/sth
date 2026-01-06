# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json

import frappe, erpnext
from frappe import _, _dict, scrub, unscrub

from frappe.model.document import Document

class DaftarBPJS(Document):

	def validate(self):
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
	doc = frappe.get_doc("Daftar BPJS","BPJS TK-PT. TRIMITRA LESTARI-00162")
	doc.before_submit()

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
				Employee.grade
				
				)
			.where(
				(Employee.unit == doc.unit)
				& (Employee.company == doc.pt)
				& (Employee.status == "Active")
				& (Employee.grade == "NON STAF" if doc.golongan == "Non Staf" else Employee.grade != "NON STAF" )
				& (SSAssignment.from_date <= doc.start_periode)
			)
		)

	list_employee = query.run()
		
	list_program_employee = {}
	susunan_bpjs = frappe.get_doc("Set Up BPJS PT", doc.set_up_bpjs)
	for satu_employee in list_employee:
		list_program_employee[satu_employee[0]] = []
		for row in susunan_bpjs.set_up_bpjs_pt_table:
			gp_satu = satu_employee[1]
			if satu_employee[10] != "NON STAF":
				gp_satu = satu_employee[1] + satu_employee[9]


			list_program_employee[satu_employee[0]].append({
				"program" : row.nama_program,
				"beban_karyawan": row.beban_karyawan / 100 * gp_satu,
				"beban_perusahaan": row.beban_perusahaan / 100 * gp_satu
			})

	doc.set_up_bpjs_detail_table = []
	doc.daftar_bpjs_employee = []

	for row in list_employee:
		gp_satu = row[1]
		if row[10] != "NON STAF":
			gp_satu = row[1] + row[9]

		satu_employee = row[0]
		gp = gp_satu
		nama_employee = row[2]
		no_ktp = row[3]
		jabatan = row[4]
		no_bpjs = row[5]
		nama_ibu = row[6]
		gol_darah = row[7]
		kelas_bpjs_kesehatan = row[8]
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
			