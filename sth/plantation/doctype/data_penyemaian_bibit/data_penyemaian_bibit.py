# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
from frappe.model.document import Document


class DataPenyemaianBibit(Document):
	def check_missing_value(self):
		if(not self.voucher_no or not self.item_code or not self.batch):
			frappe.throw(f"Purchase Receipt, Item Code, Batch cant be empty.")

		if(not self.qty_planting):
			frappe.throw(f"Qty Planting cant be zero.")
   
		if(not self.qty):
			frappe.throw(f"Grand Total Qty cant be zero.")

	def limit_qty(self):
		if(self.qty_planting<0 or self.qty_before_afkir<0):
			frappe.throw(f"Qty Planting or Qty Seed Afkir cant be negative value.")
   
		if(self.qty_planting<self.qty_before_afkir):
			frappe.throw(f"Qty Seed Afkir cant be greather than Qty Planting.")
   
		total_qty_preci = get_total_qty(self.voucher_no, self.item_code, self.batch)
		if(self.qty_planting > total_qty_preci):
			frappe.throw(f"Qty Planting must not be greater than {total_qty_preci}")

	def calculate_grand_total_qty(self):
		self.qty = flt(self.qty_planting-self.qty_before_afkir+self.qty_dobletone-self.qty_after_afkir)

	def validate(self):
		self.check_missing_value()
		self.limit_qty()
		self.calculate_grand_total_qty()
  
	def make_ste_issue(self):		
		doc = frappe.new_doc("Stock Entry")
		doc.stock_entry_type = 'Material Issue'
		doc.company = self.company
		doc.set_posting_time = 1
		doc.posting_date = self.posting_date
		doc.posting_time = self.posting_time
  
		warehouse = frappe.db.get_value(
			"Purchase Receipt Item",
			{
				"parent": self.voucher_no,
				"item_code": self.item_code,
				"batch_no": self.batch
			},
			"warehouse"
		)
		doc.from_warehouse = warehouse
  
		doc.append("items", {			
			"item_code": self.item_code,
			"qty": self.qty,
			"use_serial_batch_fields": 1,
			"batch_no": self.batch
		})
		doc.save()
		doc.submit()

		self.db_set("stock_entry", doc.name)
		self.db_set("amount", doc.total_outgoing_value)
  
	def on_submit(self):
		self.make_ste_issue()

@frappe.whitelist()
def get_item_code_preci(doctype, txt, searchfield, start, page_len, filters):
	parent = filters.get("parent") if filters else None
	if not parent:
		return []

	return frappe.db.sql("""
		SELECT 
			item_code, parent, batch_no
		FROM
			`tabPurchase Receipt Item`
		WHERE 
			item_code LIKE %(txt)s
			{parent_condition}
		LIMIT %(start)s, %(page_len)s
	""".format(
		parent_condition=" AND parent = %(parent)s" if parent else ""
	), {
		"txt": f"%{txt}%",
		"start": start,
		"page_len": page_len,
		"parent": parent
	})
 
@frappe.whitelist()
def get_batch_preci(doctype, txt, searchfield, start, page_len, filters):
	parent = filters.get("parent") if filters else None
	item_code = filters.get("item_code") if filters else None
	if not parent or not item_code:
		return []

	return frappe.db.sql("""
		SELECT 
			batch_no, item_code, parent
		FROM
			`tabPurchase Receipt Item`
		WHERE 
			parent = %(parent)s
			AND item_code = %(item_code)s
			AND item_code LIKE %(txt)s
		LIMIT %(start)s, %(page_len)s
	""", {
		"parent": parent,
		"item_code": item_code,
		"txt": f"%{txt}%",
		"start": start,
		"page_len": page_len
	})

@frappe.whitelist()
def get_total_qty(parent, item_code, batch_no):
    if not parent or not item_code or not batch_no:
        return 0

    total = frappe.db.sql("""
        SELECT SUM(qty)
        FROM `tabPurchase Receipt Item`
        WHERE parent = %(parent)s
          AND item_code = %(item_code)s
          AND batch_no = %(batch_no)s
    """, {
        "parent": parent,
        "item_code": item_code,
        "batch_no": batch_no
    })

    return total[0][0] or 0