# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe
from frappe.model.mapper import get_mapped_doc
from sth.controllers.accounts_controller import AccountsController
from frappe import _
from frappe.utils import flt
class PertanggungjawabanPerjalananDinas(AccountsController):
	def validate(self):
		# self.set_missing_value()
		super().validate()
		if self.sumber_pertanggungjawaban == "PDO":
			self.validate_pdo()

	def validate_pdo(self):
		if not self.no_pdo:
			return

		duplikat = frappe.db.get_value(
			"Pertanggungjawaban Perjalanan Dinas",
			{
				"no_pdo": self.no_pdo,
				"docstatus": ["!=", 2],
				"name": ["!=", self.name],
			},
			"name",
		)
		if duplikat:
			frappe.throw(
				_("PDO {0} sudah dipertanggungjawabkan pada {1}.").format(self.no_pdo, duplikat),
				title=_("Duplikasi Pertanggungjawaban"),
			)

		for row in self.costings:
			if flt(row.jumlah_verifikasi_hrd) > flt(row.amount):
				frappe.throw(
					_("Baris {0}: Jumlah Verifikasi HRD tidak boleh melebihi Jumlah Pengajuan {1}.").format(
						row.idx, frappe.format_value(row.amount, {"fieldtype": "Currency"})
					)
				)

	def on_submit(self):
		# Sumber PDO tidak membuat jurnal sendiri, potongannya dijurnal saat Realisasi PDO
		if self.sumber_pertanggungjawaban == "PDO":
			return

		if self.status_selisih != "Tidak Ada Selisih":
			self.make_gl_entries()

	def before_cancel(self):
		if self.sumber_pertanggungjawaban == "PDO" and self.realisasi_payment_entry:
			frappe.throw(
				_("Dokumen ini sudah dipakai pada Realisasi PDO {0}. Batalkan Payment Entry tersebut terlebih dahulu.").format(
					self.realisasi_payment_entry
				)
			)

	def on_cancel(self):
		super().on_cancel()
		if self.sumber_pertanggungjawaban == "PDO":
			return

		if self.status_selisih != "Tidak Ada Selisih":
			self.cancel_gl_entries()

	def make_gl_entries(doc, method=None):

		gl_entries = []
		akun_debit = ""
		total_debit = 0
		for row in doc.costings:
			expense_type_doc = frappe.get_doc("Expense Claim Type",row.expense_type)
			for et_baris in expense_type_doc.accounts:
				if et_baris.company == doc.company:
					akun_debit = et_baris.default_account

			# --- DEBIT ---
			gl_entries.append(
				frappe.get_doc({
					"doctype": "GL Entry",
					"posting_date": doc.posting_date,
					"account": akun_debit,
					"debit": row.sanctioned_amount,
					"credit": 0.0,
					"debit_in_account_currency": row.sanctioned_amount,
					"credit_in_account_currency": 0.0,
					"voucher_type": doc.doctype,
					"voucher_no": doc.name,
					"company": doc.company,
					"remarks": f"Pertanggungjawaban Perjalanan Dinas - {row.expense_type} - {doc.name}",
					"cost_center": frappe.get_doc("Company", doc.company).cost_center
				})
			)

			total_debit += row.sanctioned_amount

		uang_muka = 0
		if doc.total_down_amount:
			uang_muka = doc.total_down_amount

			# --- CREDIT ---
			gl_entries.append(
				frappe.get_doc({
					"doctype": "GL Entry",
					"posting_date": doc.posting_date,
					"account": doc.advance_account,
					"debit": 0.0,
					"credit": uang_muka,
					"debit_in_account_currency": 0.0,
					"credit_in_account_currency": uang_muka,
					"voucher_type": doc.doctype,
					"voucher_no": doc.name,
					"company": doc.company,
					"remarks": f"Pertanggungjawaban Perjalanan Dinas - {doc.name}",
					"is_opening": "No",
					"cost_center": frappe.get_doc("Company", doc.company).cost_center
				})
			)

		sisa = total_debit - uang_muka
		# --- CREDIT ---
		if sisa > 0:
			gl_entries.append(
				frappe.get_doc({
					"doctype": "GL Entry",
					"posting_date": doc.posting_date,
					"account": doc.credit_to,
					"debit": 0.0,
					"credit": sisa,
					"debit_in_account_currency": 0.0,
					"credit_in_account_currency": sisa,
					"voucher_type": doc.doctype,
					"voucher_no": doc.name,
					"company": doc.company,
					"remarks": f"Pertanggungjawaban Perjalanan Dinas - {doc.name}",
					"is_opening": "No",
					"cost_center": frappe.get_doc("Company", doc.company).cost_center,
					"party_type": "Employee",
					"party": doc.employee
				})
			)

		# Simpan semua GL Entry
		for gl in gl_entries:
			gl.flags.ignore_permissions = True
			gl.insert()

		frappe.msgprint(_("GL Entry berhasil dibuat."), indicator="green", alert=True)

	def cancel_gl_entries(doc, method=None):
		"""
		Batalkan (reverse) GL Entry saat dokumen di-cancel.
		"""
		frappe.db.sql(
			"""
			UPDATE `tabGL Entry`
			SET is_cancelled = 1
			WHERE voucher_type = %s
			  AND voucher_no   = %s
			  AND is_cancelled = 0
			""",
			(doc.doctype, doc.name),
		)
		frappe.msgprint(_("GL Entry berhasil dibatalkan."), indicator="orange", alert=True)

	def before_save(self):
		self.set_status_selisih()
	
	def set_status_selisih(self):
		if self.sumber_pertanggungjawaban == "PDO":
			# Tidak ada uang muka: seluruh realisasi jadi potongan saat Realisasi PDO
			self.total_down_amount = 0
			self.status_selisih = "Tidak Ada Selisih"
			self.total_selisih = 0
			self.grand_total = self.total_sanctioned_amount or 0
			self.outstanding_amount = 0
			return

		tda = self.total_down_amount or 0
		tsa = self.total_sanctioned_amount or 0

		if tsa < tda:
			self.status_selisih = "Lebih Bayar"
		elif tsa > tda:
			self.status_selisih = "Kurang Bayar"
		else:
			self.status_selisih = "Tidak Ada Selisih"

		self.total_selisih = abs(tsa - tda)
		self.grand_total = self.total_selisih
		self.outstanding_amount = self.total_selisih

	@frappe.whitelist()
	def get_data_perjalanan_dinas(self):
		if self.sumber_pertanggungjawaban == "PDO":
			self.get_data_pdo()
			return

		self.no_pdo = None
		travel = frappe.get_doc("Travel Request", self.no_spd)
		emp_advance = frappe.get_doc("Employee Advance", travel.get("custom_employee_advance"))

		if travel.tf == "Guest":
			self.guests = travel.table_dcyg

		self.get_data_employee(travel)
		self.itinerary = travel.itinerary

		# reset child table dulu
		self.costings = []

		for costing in travel.costings:
			self.append("costings", {
				"expense_type": costing.expense_type,
				"keterangan": '',
				"amount": costing.total_amount,
				"sanctioned_amount": 0
			})

		self.total_down_amount = emp_advance.get("advance_amount", 0) if emp_advance else 0
		self.advance_account = emp_advance.get("advance_account")

	def get_data_pdo(self):
		"""Tarik seluruh baris List Perjalanan Dinas dari PDO menjadi costings."""
		pdo = frappe.get_doc("Permintaan Dana Operasional", self.no_pdo)

		if not pdo.get("pdo_perjalanan_dinas"):
			frappe.throw(_("PDO {0} tidak memiliki data List Perjalanan Dinas.").format(pdo.name))

		# field yang hanya relevan untuk sumber SPD
		self.no_spd = None
		self.travel_for = None
		self.employee = None
		self.nik = None
		self.grade = None
		self.designation = None
		self.department = None
		self.itinerary = []
		self.guests = []
		self.advance_account = None
		self.total_down_amount = 0

		self.company = pdo.company
		self.cost_center = pdo.perjalanan_dinas_cost_center
		self.credit_to = pdo.perjalanan_dinas_credit_to

		self.costings = []

		for row in pdo.pdo_perjalanan_dinas:
			amount = row.revised_total or row.total or 0

			self.append("costings", {
				"expense_type": row.type,
				"pengguna": row.employee,
				"description": row.needs,
				"amount": amount,
				"sanctioned_amount": 0,
				"jumlah_verifikasi_hrd": 0,
				"pdo_child_name": row.name,
			})

		self.total_claimed_amount = 0
		self.total_sanctioned_amount = 0

	def get_data_employee(self, travel):
		employee = frappe.get_doc("Employee", travel.get("employee"))
		designation = frappe.get_doc("Designation", employee.designation)

		self.travel_for = travel.get("tf")
		self.employee = employee.get("name")
		self.employee = employee.get("name")
		self.nik = employee.get("name")
		self.grade = employee.get("grade")
		self.designation = designation.get("designation_name")
		self.department = employee.get("department")
		self.company = employee.get("company")
  
@frappe.whitelist()
def make_payment_entry(source_name, target_doc=None):
	def post_process(source, target):
		employee = frappe.db.get_value("Employee", source.employee, "*")
		company = frappe.db.get_value("Company", source.company, "*")

		if source.status_selisih == "Lebih Bayar":
			target.payment_type = "Receive"
		elif source.status_selisih == "Kurang Bayar":
			target.payment_type = "Pay"
	
		target.party_type = "Employee"
		target.party = employee.name
		target.party_name = employee.employee_name
		target.no_rekening = employee.bank_ac_no
		target.nama_bank = employee.nama_bank
		target.unit = employee.unit
		target.no_rekening_tujuan = employee.bank_ac_no
		target.bank_tujuan = employee.bank_name
		target.paid_amount = source.outstanding_amount
		target.paid_from_account_currency = "IDR"
		target.paid_to_account_currency = "IDR"
		target.received_amount = source.outstanding_amount
		target.append("references", {
			"reference_doctype": "Pertanggungjawaban Perjalanan Dinas",
			"reference_name": source.name,
			"total_amount": source.grand_total,
			"outstanding_amount": source.outstanding_amount,
			"allocated_amount": source.outstanding_amount
		})

	doclist = get_mapped_doc(
		"Pertanggungjawaban Perjalanan Dinas",
		source_name,
		{
			"Pertanggungjawaban Perjalanan Dinas": {
				"doctype": "Payment Entry",
				"field_map": {
					"salary_account": "paid_from",
					"credit_to": "paid_to",
				}
			}
		},
		target_doc,
		post_process,
	)
 
	return doclist