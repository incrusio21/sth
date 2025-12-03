# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
import erpnext

from frappe import _, scrub
from sth.controllers.accounts_controller import AccountsController

class PDODanaCadanganVtwo(AccountsController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._expense_account = "debit_to"

	def on_submit(self):
		self.make_gl_entry()

	def on_cancel(self):
		super().on_cancel()
		self.make_gl_entry()

	def get_gl_entries(self):
		gl_entries = []

		self.make_party_gl_entry(gl_entries)
		self.make_salary_gl_entry(gl_entries)

		return gl_entries

	def make_party_gl_entry(self, gl_entries):
		against = []
		datas = self.get('pdo_dana_cadangan_vtwo')
		for row in datas:
			fund_type = row.get('fund_type')
			if fund_type in against:
				continue
			against.append(fund_type)

		gl_entries.append(
			self.get_gl_dict(
				{
					"account": self.credit_to,
					"against": ", ".join(against),
					"credit": self.grand_total,
					"credit_in_account_currency": self.grand_total,
					"cost_center": self.cost_center,
					"party_type": self._party_type,
					"party": self.get(scrub(self._party_type)),
					"against_voucher": self.name,
					"against_voucher_type": self.doctype,	
				},
				item=self,
			)
		)

	def make_salary_gl_entry(self, gl_entries):
		cost_center = erpnext.get_default_cost_center(self.company)
		datas = self.get('pdo_dana_cadangan_vtwo')
		accounts_merge = {}

		for row in datas:
			fund_type = row.get('fund_type')
			revised_amount = row.get('revised_amount')

			if fund_type in accounts_merge:
				accounts_merge[fund_type] += revised_amount
			else:
				accounts_merge[fund_type] = revised_amount

		for account, total in accounts_merge.items():
			gl_entries.append(
				self.get_gl_dict(
					{
						"account": account,
						"against": self.get(scrub(self._party_type)) or self.credit_to,
						"debit": total,
						"debit_in_account_currency": total,
						"cost_center": cost_center,
					},
					item=self,
				)
			)


def process_pdo_dana_cadangan(data, childs):
	pdo_dana_cadangan = frappe.db.get_value("PDO Dana Cadangan Vtwo", {
		'reference_doc': data['reference_doc'],
		'reference_name': data['reference_name']
	}, "*")
	
	if pdo_dana_cadangan:
		update_pdo_dana_cadangan(pdo_dana_cadangan, data, childs)
	else:
		make_pdo_dana_cadangan(data, childs)

def make_pdo_dana_cadangan(data, childs):
	data.update({
		"doctype": "PDO Dana Cadangan Vtwo",
		"naming_series": "DC-"
	})
	
	doc = frappe.get_doc(data)
	
	doc = insert_childs(doc, childs)
	doc.insert(ignore_permissions=True)

	update_transaction_number(doc, data, childs)

def update_pdo_dana_cadangan(pdo_dana_cadangan, data, childs):
	doc = frappe.get_doc("PDO Dana Cadangan Vtwo", pdo_dana_cadangan.name)
	if not childs:
		doc.delete()
		update_transaction_number(doc, data, childs)
	else:
		doc.update(data)
		doc.set("pdo_dana_cadangan_vtwo", [])
		doc = insert_childs(doc, childs)
		doc.save()

def insert_childs(doc, childs):
	for row in childs:
		doc.append("pdo_dana_cadangan_vtwo", {
			"fund_type": row.fund_type,
			"amount": row.amount,
			"revised_amount": row.revised_amount,
			"cash_bank_balance_adjustment": row.cash_bank_balance_adjustment
		})

	return doc

def update_transaction_number(doc, data, childs):
	main_pdo = frappe.get_doc(data['reference_doc'], data['reference_name'])
	main_pdo.dana_cadangan_transaction_number = doc.name if childs else None
	main_pdo.db_update()