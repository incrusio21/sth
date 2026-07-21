# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.utils import flt
from frappe.model.mapper import get_mapped_doc

import erpnext
from erpnext.accounts.general_ledger import merge_similar_entries

from sth.controllers.accounts_controller import AccountsController

class GantiRugiLahan(AccountsController):
	def document_kriteria(self):
		return self.jenis_biaya or "GRLTT"
	
	def validate(self):
		self.set_missing_value()
		self.validate_duplicate_sppt()
		self.calculate_total()
		self.set_no_rekening()
		self.validate_payment_schedule()
		super().validate()

	def set_no_rekening(self):
		if not self.items:
			return

		row = self.items[0]

		if not row.sppt:
			return

		pemilik = frappe.db.get_value(
			"GIS",
			row.sppt,
			"pemilik_lahan"
		)

		if not pemilik:
			return

		norek = frappe.db.get_value(
			"Daftar Masyarakat",
			pemilik,
			"norek"
		)

		if norek:
			self.no_rekening = norek
	
	def validate_duplicate_sppt(self):
		sppt = []
		for i in self.items:
			if i.perangkat_desa == "Ya":
				continue
			
			if i.sppt in sppt:
				frappe.throw(f"No SPPT {i.sppt} already used")

			if frappe.get_cached_value("GIS", i.sppt, "perangkat_desa") != i.perangkat_desa:
				frappe.throw(f"No SPPT {i.sppt} have diffrent Perangkat Desa")

			sppt.append(i.sppt)
			
	def calculate_total(self):
		grand_total = 0
		for i in self.items:
			i.amount = flt(i.qty) * flt(i.rate) + flt(i.biaya_surat)
			grand_total += i.amount

		self.grand_total = flt(grand_total)

	def validate_payment_schedule(self):
		total_portion = 0
		total_payment = 0
		for d in self.payment_schedule:
			total_portion += flt(d.invoice_portion)
			total_payment += flt(d.payment_amount)

		if total_portion > 100:
			frappe.throw(f"Total Invoice Portion tidak boleh lebih dari 100% (saat ini {total_portion}%)")

		self.total_invoice_portion = flt(total_portion)
		self.total_payment_amount = flt(total_payment)

	def on_submit(self):
		pass

	def on_cancel(self):
		super().on_cancel()

	def get_gl_entries(self):
		gl_entries = []

		self.make_party_gl_entry(gl_entries)
		self.make_salary_gl_entry(gl_entries)

		gl_entries = merge_similar_entries(gl_entries)
		
		return gl_entries
	
	def make_salary_gl_entry(self, gl_entries):
		cost_center = erpnext.get_default_cost_center(self.company)

		for d in self.items:
			gl_entries.append(
				self.get_gl_dict(
					{
						"account": d.expense_account,
						"against": self.get("employee") or self.credit_to,
						"debit": d.amount,
						"debit_in_account_currency": d.amount,
						"cost_center": cost_center		
					},
					item=d,
				)
			)

@frappe.whitelist()
def get_details_sppt(childrens, pembayaran_lahan, as_dict=False):
	if isinstance(childrens, str):
		childrens = json.loads(childrens)

	fields = ["pemilik_lahan"]
	if pembayaran_lahan == "Lahan":
		fields.append("total_lahan")
	else:
		fields.append("luas_tanam")

	for ch in childrens:
		gis = frappe.db.get_value("GIS", ch.get("sppt"), fields)
		ch.update({
			"pemilik_lahan": gis[0],
			"qty": gis[1],
		})

	ress = {"childrens": childrens}
	if as_dict:
		ress = childrens

	return ress 

@frappe.whitelist()
def get_details_jenis_biaya(childrens, company, sppt_update=False, as_dict=False):
	if isinstance(childrens, str):
		childrens = json.loads(childrens)
	
	jenis_biaya = [d.get("jenis_biaya") for d in childrens]
	if not jenis_biaya:
		return childrens
	
	# load detail kegiatan
	def _get_grl_details():
		agrl = frappe.qb.DocType("Account Ganti Rugi Lahan")

		result = (
			frappe.qb.from_(agrl)
			.select(
				agrl.parent, agrl.account, 
			)
			.where(
				(agrl.company == company) &
				(agrl.parent.isin(jenis_biaya))
			)
		).run()

		return {row[0] : frappe._dict(zip([
			"expense_account"
		], row[1:], strict=False)) for row in result}

	grl_details = _get_grl_details()

	for ch in childrens:
		if sppt_update:
			ch.update({"sppt": None})

		# update table dengan details grl
		if grl := grl_details.get(ch.get("jenis_biaya")):
			ch.update(grl)

	ress = {"childrens": childrens}
	if as_dict:
		ress = childrens

	return ress

@frappe.whitelist()
def ajukan_termin(name):
	row = frappe.get_doc("Proposal Schedule", name)

	if row.parenttype != "Ganti Rugi Lahan":
		frappe.throw("Termin ini bukan bagian dari Ganti Rugi Lahan.")

	if frappe.db.get_value("Ganti Rugi Lahan", row.parent, "docstatus") != 1:
		frappe.throw("Dokumen Ganti Rugi Lahan harus berstatus Submitted sebelum termin bisa diajukan.")

	if row.diajukan:
		frappe.throw("Termin ini sudah diajukan.")

	first_not_diajukan = frappe.get_all(
		"Proposal Schedule",
		filters={"parenttype": "Ganti Rugi Lahan", "parent": row.parent, "diajukan": 0},
		fields=["name"],
		order_by="idx asc",
		limit=1,
	)

	if first_not_diajukan and first_not_diajukan[0].name != name:
		frappe.throw("Termin harus diajukan secara berurutan, mulai dari baris pertama yang belum diajukan.")

	frappe.db.set_value("Proposal Schedule", name, "diajukan", 1)

	return True

@frappe.whitelist()
def get_next_payment_schedule(reference_doctype, reference_name, exclude_payment_entry=None):
	filters = {"parenttype": reference_doctype, "parent": reference_name}
	if reference_doctype == "Ganti Rugi Lahan":
		filters["diajukan"] = 1

	schedule = frappe.get_all(
		"Proposal Schedule",
		filters=filters,
		fields=["name", "payment_term", "payment_amount", "outstanding"],
		order_by="idx asc",
	)

	if not schedule:
		frappe.throw(f"Belum ada termin yang diajukan untuk {reference_doctype} {reference_name}")

	per = frappe.qb.DocType("Payment Entry Reference")
	pe = frappe.qb.DocType("Payment Entry")

	query = (
		frappe.qb.from_(per)
		.join(pe).on(pe.name == per.parent)
		.select(per.name)
		.where(
			(per.reference_doctype == reference_doctype)
			& (per.reference_name == reference_name)
			& (pe.docstatus == 1)
		)
	)

	if exclude_payment_entry:
		query = query.where(pe.name != exclude_payment_entry)

	used_count = len(query.run())

	if used_count >= len(schedule):
		frappe.throw(f"Semua termin yang diajukan untuk {reference_name} sudah digunakan")

	term = schedule[used_count]

	return {
		"payment_term": term.payment_term,
		"allocated_amount": flt(term.outstanding or term.payment_amount),
		"payment_term_outstanding": flt(term.outstanding),
	}

@frappe.whitelist()
def fetch_company_account(company, childrens=None):
	accounts_dict = {
		"credit_to": frappe.get_cached_value("Company", company, "ganti_rugi_lahan_account"),
	}

	if childrens:
		accounts_dict.update(get_details_jenis_biaya(childrens, company))

	return accounts_dict

@frappe.whitelist()
def make_payment_entry(source_name, target_doc=None):
	def post_process(source, target):
		if not source.items:
			frappe.throw("Ganti Rugi Lahan tidak memiliki items")

		schedule = get_next_payment_schedule("Ganti Rugi Lahan", source.name)
		# expense_account = source.items[0].expense_account
		expense_account = source.credit_to
		party_account_currency = frappe.get_cached_value("Account", expense_account, "account_currency")

		target.payment_type = "Pay"
		target.party_type = "Employee"
		target.party = source.employee
		target.naming_series = "ACC-PAY-.YYYY.-"
		target.party_name = frappe.get_cached_value("Employee", source.employee, "employee_name")
		target.paid_to = expense_account
		target.paid_to_account_currency = party_account_currency
		target.paid_amount = schedule.get("allocated_amount")
		target.received_amount = schedule.get("allocated_amount")

		target.append("references", {
			"reference_doctype": "Ganti Rugi Lahan",
			"reference_name": source.name,
			"payment_term": schedule.get("payment_term"),
			"total_amount": source.grand_total,
			"outstanding_amount": schedule.get("payment_term_outstanding"),
			"allocated_amount": schedule.get("allocated_amount"),
		})

	doclist = get_mapped_doc(
		"Ganti Rugi Lahan",
		source_name,
		{
			"Ganti Rugi Lahan": {
				"doctype": "Payment Entry",
				"field_map": {
					"company": "company",
					"cost_center": "cost_center",
				},
			}
		},
		target_doc,
		post_process,
	)

	return doclist