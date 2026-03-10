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


@frappe.whitelist()
def get_history_purchase_request(asset):
    from erpnext.accounts.utils import get_fiscal_year
    today = frappe.utils.today()
    fiscal_year = get_fiscal_year(date=today,boolean=True)
    start_year = fiscal_year[0][1]

    return frappe.db.sql("""
        SELECT poi.item_code, poi.item_name, po.name as no_po, po.transaction_date as tanggal, poi.qty, poi.rate, poi.amount, poi.material_request as no_mr, mri.km_hm
        FROM `tabPurchase Order` po
        JOIN `tabPurchase Order Item` poi on poi.parent = po.name
        JOIN `tabMaterial Request Item` mri on mri.name = poi.material_request_item
		JOIN `tabAlat Berat Dan Kendaraan` k on k.name = mri.kendaraan
        WHERE po.docstatus = 1 AND k.no_pol = %s AND po.transaction_date BETWEEN %s AND %s
		ORDER BY po.transaction_date,po.name
    """,(asset,start_year,today),as_dict=True)