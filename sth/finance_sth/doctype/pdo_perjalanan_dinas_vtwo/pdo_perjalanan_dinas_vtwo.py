# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PDOPerjalananDinasVtwo(Document):
	pass

def process_pdo_perjalanan_dinas(data, childs):
	pdo_perjalanan_dinas = frappe.db.get_value("PDO Perjalanan Dinas Vtwo", {
		'reference_doc': data['reference_doc'],
		'reference_name': data['reference_name']
	}, "*")
	
	if pdo_perjalanan_dinas:
		update_pdo_perjalanan_dinas(pdo_perjalanan_dinas, data, childs)
	else:
		make_pdo_perjalanan_dinas(data, childs)

def make_pdo_perjalanan_dinas(data, childs):
	data.update({
		"doctype": "PDO Perjalanan Dinas Vtwo",
		"naming_series": "PD-"
	})
	
	doc = frappe.get_doc(data)
	
	doc = insert_childs(doc, childs)
	doc.insert(ignore_permissions=True)

	update_transaction_number(doc, data, childs)

def update_pdo_perjalanan_dinas(pdo_perjalanan_dinas, data, childs):
	doc = frappe.get_doc("PDO Perjalanan Dinas Vtwo", pdo_perjalanan_dinas.name)
	if not childs:
		doc.delete()
		update_transaction_number(doc, data, childs)
	else:
		doc.update(data)
		doc.set("pdo_perjalanan_dinas_vtwo", [])
		doc = insert_childs(doc, childs)
		doc.save()

def insert_childs(doc, childs):
	for row in childs:
		doc.append("pdo_perjalanan_dinas_vtwo", {
			"employee": row.employee,
			"sub_detail": row.sub_detail,
			"license_plate_number": row.license_plate_number,
			"type": row.type,
			"hari_dinas": row.hari_dinas,
			"plafon": row.plafon,
			"revised_duty_day": row.revised_duty_day,
			"revised_plafon": row.revised_plafon,
			"needs": row.needs,
			"total": row.total,
			"revised_total": row.revised_total,
		})

	return doc

def update_transaction_number(doc, data, childs):
	main_pdo = frappe.get_doc(data['reference_doc'], data['reference_name'])
	main_pdo.perjalanan_dinas_transaction_number = doc.name if childs else None
	main_pdo.db_update()