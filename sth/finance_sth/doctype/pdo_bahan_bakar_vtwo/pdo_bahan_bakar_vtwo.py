# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PDOBahanBakarVtwo(Document):
	pass

def process_pdo_bahan_bakar(data, childs):
	pdo_bahan_bakar = frappe.db.get_value("PDO Bahan Bakar Vtwo", {
		'reference_doc': data['reference_doc'],
		'reference_name': data['reference_name']
	}, "*")
	
	if pdo_bahan_bakar:
		update_pdo_bahan_bakar(pdo_bahan_bakar, data, childs)
	else:
		make_pdo_bahan_bakar(data, childs)

def make_pdo_bahan_bakar(data, childs):
	data.update({
		"doctype": "PDO Bahan Bakar Vtwo",
		"naming_series": "BB-"
	})
	
	doc = frappe.get_doc(data)
	
	doc = insert_childs(doc, childs)
	doc.insert(ignore_permissions=True)

	update_transaction_number(doc, data, childs)

def update_pdo_bahan_bakar(pdo_bahan_bakar, data, childs):
	doc = frappe.get_doc("PDO Bahan Bakar Vtwo", pdo_bahan_bakar.name)
	if not childs:
		doc.delete()
		update_transaction_number(doc, data, childs)
	else:
		doc.update(data)
		doc.set("pdo_bahan_bakar_vtwo", [])
		doc = insert_childs(doc, childs)
		doc.save()

def insert_childs(doc, childs):
	for row in childs:
		doc.append("pdo_bahan_bakar_vtwo", {
			"employee": row.employee,
			"designation": row.designation,
			"plafon": row.plafon,
			"unit_price": row.unit_price,
			"revised_plafon": row.revised_plafon,
			"revised_unit_price": row.revised_unit_price,
			"needs": row.needs,
			"price_total": row.price_total,
			"revised_price_total": row.revised_price_total,
		})

	return doc

def update_transaction_number(doc, data, childs):
	main_pdo = frappe.get_doc(data['reference_doc'], data['reference_name'])
	main_pdo.db_set('bahan_bakar_transaction_number', doc.name if childs else None)