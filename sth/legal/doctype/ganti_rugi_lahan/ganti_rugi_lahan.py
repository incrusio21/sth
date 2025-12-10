# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.utils import flt

import erpnext
from erpnext.accounts.general_ledger import merge_similar_entries

from sth.controllers.accounts_controller import AccountsController

class GantiRugiLahan(AccountsController):
	def validate(self):
		self.set_missing_value()
		self.validate_duplicate_sppt()
		self.calculate_total()
		super().validate()

	def validate_duplicate_sppt(self):
		sppt = []
		for i in self.items:
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

	def on_submit(self):
		self.make_gl_entry()

	def on_cancel(self):
		super().on_cancel()
		self.make_gl_entry()
	
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
def fetch_company_account(company, childrens=None):
	accounts_dict = {
		"credit_to": frappe.get_cached_value("Company", company, "ganti_rugi_lahan_account"),
	}
	
	if childrens:
		accounts_dict.update(get_details_jenis_biaya(childrens, company))

	return accounts_dict