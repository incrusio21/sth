# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class DaftarBPJS(Document):
	@frappe.whitelist()
	def get_employee(self):
		pasang_bpjs(self)
		self.save()


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
			 	Employee.blood_group
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
			list_program_employee[satu_employee[0]].append({
				"program" : row.nama_program,
				"beban_karyawan": row.beban_karyawan / 100 * satu_employee[1],
				"beban_perusahaan": row.beban_perusahaan / 100 * satu_employee[1]
			})

	doc.set_up_bpjs_detail_table = []
	doc.daftar_bpjs_employee = []

	for row in list_employee:
		satu_employee = row[0]
		gp = row[1]
		nama_employee = row[2]
		no_ktp = row[3]
		jabatan = row[4]
		no_bpjs = row[5]
		nama_ibu = row[6]
		gol_darah = row[7]
		beban_karyawan = 0
		beban_perusahaan = 0
		# masukkan semua detil ke table detail
		for satu_beban in list_program_employee[satu_employee]:
			satu_row = doc.append("set_up_bpjs_detail_table")
			
			satu_row.employee = satu_employee
			satu_row.program = satu_beban.get("program")
			satu_row.beban_karyawan = satu_beban.get("beban_karyawan")
			satu_row.beban_perusahaan = satu_beban.get("beban_perusahaan")

			beban_karyawan += frappe.utils.flt(satu_row.beban_karyawan)
			beban_perusahaan += frappe.utils.flt(satu_row.beban_perusahaan)


		# masuk ke daftar bpjs employee
		satu_row_employee = doc.append("daftar_bpjs_employee")
		satu_row_employee.employee = satu_employee
		satu_row_employee.nama = nama_employee
		satu_row_employee.gp = gp
		satu_row_employee.beban_karyawan = beban_karyawan
		satu_row_employee.beban_perusahaan = beban_perusahaan
		satu_row_employee.jumlah = beban_perusahaan + beban_karyawan

		satu_row_employee.no_ktp = no_ktp
		satu_row_employee.jabatan = jabatan
		satu_row_employee.no_bpjs_tkkes = no_bpjs
		satu_row_employee.nama_ibu_kandung = nama_ibu
		satu_row_employee.gol_darah = gol_darah
			