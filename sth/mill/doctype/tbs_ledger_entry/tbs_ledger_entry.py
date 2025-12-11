# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

from operator import index
import frappe
from frappe.model.document import Document
from frappe.utils import today,add_days

class TBSLedgerEntry(Document):
	pass

def create_tbs_ledger(data):
	doc = frappe.new_doc("TBS Ledger Entry")
	doc.update(data)
	doc.actual_qty = calculate_actual_qty(data)
	doc.insert()
	doc.submit()

	last_posting = frappe.db.get_all("TBS Ledger Entry",["posting_date"],{"item_code": doc.item_code, "is_cancelled": 0 },order_by="posting_datetime desc",limit=1, pluck="posting_date")
	last_posting = last_posting[0] if last_posting else None

	if doc.posting_date != last_posting:
		from_date = add_days(doc.posting_date,-1)
		repost_qty_tbs(from_date,doc.item_code)


def calculate_actual_qty(data):
	last_qty = 0
	last_ledger =  frappe.db.sql("""
		select tle.actual_qty from `tabTBS Ledger Entry` tle
		where tle.item_code = %s and tle.posting_datetime < %s and tle.is_cancelled = 0
		order by tle.posting_datetime
		limit 1
		FOR UPDATE
	""",[data.item_code, data.posting_datetime],as_dict=True)
	
	if last_ledger:
		last_qty = last_ledger[0].actual_qty

	return last_qty + data.balance_qty


def repost_qty_tbs(from_date,item_code):
	tbs_ledger = frappe.db.get_all("TBS Ledger Entry",["name","balance_qty","actual_qty"],{"posting_datetime":[">=",from_date],"item_code":item_code,"is_cancelled":0})

	balance_qty = actual_qty = 0
	for index,row in enumerate(tbs_ledger):
		if index == 0:
			actual_qty = row.actual_qty
		else:
			new_actual_qty = balance_qty + actual_qty
			frappe.db.set_value("TBS Ledger Entry", row.name,"actual_qty",new_actual_qty)
			
			actual_qty = new_actual_qty
		
		balance_qty = row.balance_qty

def reverse_tbs_ledger(voucher_no):
	frappe.db.sql("""
		UPDATE `tabTBS Ledger Entry`
		SET is_cancelled = 1
		WHERE voucher_no = %s
	""", (voucher_no))
