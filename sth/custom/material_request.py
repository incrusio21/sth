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
		JOIN `tabMaterial Request` mr on mr.name = po.material_request
        JOIN `tabMaterial Request Item` mri on mri.name = poi.material_request_item
		JOIN `tabAlat Berat Dan Kendaraan` k on k.name = mri.kendaraan
        WHERE po.docstatus = 1 AND mr.sub_purchase_type = "Service Request" AND k.no_pol = %s AND po.transaction_date BETWEEN %s AND %s
		ORDER BY po.transaction_date,po.name
    """,(asset,start_year,today),as_dict=True)


def calculate_percent_quoted(self,method):
	pr_sr = set([ r.material_request for r in self.items ])
	for name in pr_sr:
		percent_quotation = get_percent_quotation_created(name)
		doc = frappe.get_doc("Material Request",name)
		doc.db_set("per_quotation",percent_quotation)
		set_pr_sr_status(doc)

def get_percent_quotation_created(name):
	quotation_created = frappe.db.sql("""
		select count(*) as total_created
		from `tabMaterial Request Item` mri
		left join `tabRequest for Quotation Item` rfqi on rfqi.material_request_item = mri.name
		left join `tabSupplier Quotation Item` sqi on sqi.material_request_item = mri.name
		where mri.parent = %s and (rfqi.name is not null or sqi.name is not null)
	""",(name),as_dict=True)

	created = quotation_created[0].total_created
	total_item = frappe.db.get_value("Material Request Item",fieldname=["count(*) as total_item"],filters={"parent": name})

	return created / total_item * 100

# set custom status untuk
def set_pr_sr_status(doc,method=None):
	status = None
	if doc.per_ordered == 0 and doc.per_received == 0:
		if doc.per_quotation == 0:
			status = "Not Quoted"
		elif doc.per_quotation < 100:
			status = "Partially Quoted"
		elif doc.per_quotation == 100 and doc.per_ordered == 0:
			status = "Fully Quoted"
	
	if status:
		doc.db_set("status",status)