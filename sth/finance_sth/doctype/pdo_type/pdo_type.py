# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PDOType(Document):
	pass

@frappe.whitelist()
def filter_link_pdo_type(doctype, txt, searchfield, start, page_len, filters):
    type_category = frappe.qb.DocType("PDO Category Type Table")
    query = (
		frappe.qb.from_(type_category)
		.select(type_category.parent.as_("value"))
		.where((type_category.category == filters.get("category")) & (type_category.parent.like(f'%{txt}%')))
	)
    
    res = query.run()
    
    return res