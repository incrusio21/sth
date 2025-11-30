# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe

from sth.controllers.accounts_controller import AccountsController

class PDONONPDOVtwo(AccountsController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._expense_account = "debit_to"

	def on_submit(self):
		self.make_gl_entry()

	def on_cancel(self):
		super().on_cancel()
		self.make_gl_entry()

def process_pdo_non_pdo(data, childs):
	pdo_non_pdo = frappe.db.get_value("PDO NON PDO Vtwo", {
		'reference_doc': data['reference_doc'],
		'reference_name': data['reference_name']
	}, "*")
	
	if pdo_non_pdo:
		update_pdo_non_pdo(pdo_non_pdo, data, childs)
	else:
		make_pdo_non_pdo(data, childs)

def make_pdo_non_pdo(data, childs):
	data.update({
		"doctype": "PDO NON PDO Vtwo",
		"naming_series": "NPDO-"
	})
	
	doc = frappe.get_doc(data)
	
	doc = insert_childs(doc, childs)
	doc.insert(ignore_permissions=True)

	update_transaction_number(doc, data, childs)

def update_pdo_non_pdo(pdo_non_pdo, data, childs):
	doc = frappe.get_doc("PDO NON PDO Vtwo", pdo_non_pdo.name)
	if not childs:
		doc.delete()
		update_transaction_number(doc, data, childs)
	else:
		doc.update(data)
		doc.set("pdo_non_pdo_vtwo", [])
		doc = insert_childs(doc, childs)
		doc.save()

def insert_childs(doc, childs):
	for row in childs:
		doc.append("pdo_non_pdo_vtwo", {
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
		})

	return doc

def update_transaction_number(doc, data, childs):
	main_pdo = frappe.get_doc(data['reference_doc'], data['reference_name'])
	main_pdo.non_pdo_transaction_number = doc.name if childs else None
	main_pdo.db_update()