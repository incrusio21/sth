import frappe
from frappe import _

def update_ba_reference(doc,method):
	if doc.berita_acara:
		if method == "on_submit":
			frappe.db.set_value("Berita Acara",doc.berita_acara,"material_request",doc.name,update_modified=False)
		elif method == "on_cancel":
			frappe.db.set_value("Berita Acara",doc.berita_acara,"material_request","",update_modified=False)


@frappe.whitelist()
def get_material_request_items_query(doctype, txt, searchfield, start, page_len, filters):
	 
	conditions = ""
	
	return frappe.db.sql("""
		SELECT DISTINCT
			mri.item_code,
			mri.item_name,
			mri.qty,
			mri.uom,
			mri.unit
		FROM `tabMaterial Request Item` mri
		INNER JOIN `tabMaterial Request` mr ON mr.name = mri.parent
		WHERE
			mr.docstatus = 1
			AND mr.material_request_type = 'Purchase'
			AND mr.status != 'Stopped'
			AND mr.per_ordered < 100
			AND (mri.item_code LIKE %(txt)s OR mri.item_name LIKE %(txt)s)
			AND mri.name NOT IN (select material_request_item FROM `tabRequest for Quotation Item`)
			{conditions}
		ORDER BY
			mri.item_code
		LIMIT %(start)s, %(page_len)s
	""".format(conditions=conditions), {
		'txt': f"%{txt}%",
		'start': start,
		'page_len': page_len
	})