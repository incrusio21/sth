# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe

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