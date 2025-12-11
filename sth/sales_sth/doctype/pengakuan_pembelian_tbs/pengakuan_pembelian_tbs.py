
import frappe
from frappe.model.document import Document
from frappe import _

class PengakuanPembelianTBS(Document):
	pass

@frappe.whitelist()
def get_purchase_order_items(nama_supplier):

	if not nama_supplier:
		frappe.throw(_("Supplier name is required"))

	po_items = frappe.db.sql("""
		SELECT 
			poi.item_code,
			poi.item_name,
			poi.qty,
			poi.rate,
			poi.amount as total
		FROM 
			`tabPurchase Order Item` poi
		JOIN 
			`tabPurchase Order` po ON poi.parent = po.name
		WHERE 
			po.supplier = %s
			AND po.docstatus = 1
		ORDER BY 
			po.transaction_date DESC, poi.idx
	""", (nama_supplier,), as_dict=1)

	return po_items

	