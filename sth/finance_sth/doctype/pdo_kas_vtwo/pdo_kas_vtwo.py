# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe

import erpnext

from frappe import _, scrub
from sth.controllers.accounts_controller import AccountsController


class PDOKasVtwo(AccountsController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._expense_account = "debit_to"

	# def on_submit(self):
	# 	self.make_gl_entry()

	# def on_cancel(self):
	# 	super().on_cancel()
	# 	self.make_gl_entry()

	def get_gl_entries(self):
		gl_entries = []

		self.make_party_gl_entry(gl_entries)
		self.make_salary_gl_entry(gl_entries)

		return gl_entries

	def make_party_gl_entry(self, gl_entries):
		against = []
		datas = self.get('pdo_kas_vtwo')
		for row in datas:
			debit_to = row.get('debit_to')
			if debit_to in against:
				continue
			against.append(debit_to)

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
		datas = self.get('pdo_kas_vtwo')
		accounts_merge = {}

		for row in datas:
			debit_to = row.get('debit_to')
			revised_total = row.get('revised_total')

			if debit_to in accounts_merge:
				accounts_merge[debit_to] += revised_total
			else:
				accounts_merge[debit_to] = revised_total

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


def process_pdo_kas(data, childs):
	pdo_kas = frappe.db.get_value("PDO Kas Vtwo", {
		'reference_doc': data['reference_doc'],
		'reference_name': data['reference_name']
	}, "*")
	
	if pdo_kas:
		update_pdo_kas(pdo_kas, data, childs)
	else:
		make_pdo_kas(data, childs)

def make_pdo_kas(data, childs):
	data.update({
		"doctype": "PDO Kas Vtwo",
		"naming_series": "KAS-"
	})
	
	doc = frappe.get_doc(data)
	
	doc = insert_childs(doc, childs)
	doc.insert(ignore_permissions=True)

	update_transaction_number(doc, data, childs)

def update_pdo_kas(pdo_kas, data, childs):
	doc = frappe.get_doc("PDO Kas Vtwo", pdo_kas.name)
	if not childs:
		doc.delete()
		update_transaction_number(doc, data, childs)
	else:
		doc.update(data)
		doc.set("pdo_kas_vtwo", [])
		doc = insert_childs(doc, childs)
		doc.save()

def insert_childs(doc, childs):
	for row in childs:
		doc.append("pdo_kas_vtwo", {
			"employee": row.employee,
			"sub_detail": row.sub_detail,
			"type": row.type,
			"item_code": row.item_code,
			"item_name": row.item_name,
			"uom": row.uom,
			"qty": row.qty,
			"price": row.price,
			"revised_qty": row.revised_qty,
			"revised_price": row.revised_price,
			"needs": row.needs,
			"total": row.total,
			"revised_total": row.revised_total,
			"routine_type": row.routine_type,
			"debit_to": row.debit_to,
		})

	return doc

def update_transaction_number(doc, data, childs):
	main_pdo = frappe.get_doc(data['reference_doc'], data['reference_name'])
	main_pdo.kas_transaction_number = doc.name if childs else None
	main_pdo.db_update()