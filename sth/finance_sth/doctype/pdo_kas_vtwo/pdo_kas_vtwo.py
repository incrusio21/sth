# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PDOKasVtwo(Document):
	pass

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
		})

	return doc

def update_transaction_number(doc, data, childs):
	main_pdo = frappe.get_doc(data['reference_doc'], data['reference_name'])
	main_pdo.kas_transaction_number = doc.name if childs else None
	main_pdo.db_update()