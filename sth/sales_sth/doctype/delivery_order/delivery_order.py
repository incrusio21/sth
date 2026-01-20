# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from erpnext.stock.doctype.delivery_note.delivery_note import DeliveryNote
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, nowdate, nowtime
import json

class DeliveryOrder(DeliveryNote):
	def on_submit(self):
		pass

	def on_cancel(self):
		pass


@frappe.whitelist()
def make_delivery_note(source_name, target_doc=None, transporter_data=None):

	if isinstance(transporter_data, str):
		transporter_data = json.loads(transporter_data) if transporter_data != 'null' else None
	
	def set_missing_values(source, target):
		"""Set nilai-nilai yang diperlukan untuk Delivery Note"""
		target.posting_date = nowdate()
		target.posting_time = nowtime()
		
		# Set transporter info jika ada
		if transporter_data:
			target.transporter = transporter_data.get('transporter')
			target.transporter_name = transporter_data.get('transporter_name')
			target.lr_date = transporter_data.get('transport_receipt_date')
			target.vehicle_no = transporter_data.get('vehicle_no')
			target.driver_name = transporter_data.get('driver_name')
			target.driver = transporter_data.get('driver')  # Untuk field driver jika ada
			
			# Custom fields lainnya jika ada
			if transporter_data.get('driver_contact'):
				target.driver_contact = transporter_data.get('driver_contact')
		
		# Set reference ke Delivery Order
		target.delivery_order = source.name
		
		# Run method bawaan jika ada
		if hasattr(target, 'set_missing_values'):
			target.run_method("set_missing_values")
		
		if hasattr(target, 'calculate_taxes_and_totals'):
			target.run_method("calculate_taxes_and_totals")
	
	def update_item(source, target, source_parent):
		"""Update item dari Delivery Order ke Delivery Note"""
		target.qty = source.qty
		target.stock_qty = source.qty
		
		# Set warehouse
		if source.warehouse:
			target.warehouse = source.warehouse
		elif source_parent.set_warehouse:
			target.warehouse = source_parent.set_warehouse
		
		# Set reference ke Delivery Order
		target.delivery_order = source_parent.name
		target.delivery_order_item = source.name
		
		# Set reference ke Sales Order jika ada
		if source.against_sales_order:
			target.against_sales_order = source.against_sales_order
			target.so_detail = source.so_detail
	
	# Mapping configuration
	doclist = get_mapped_doc(
		"Delivery Order",
		source_name,
		{
			"Delivery Order": {
				"doctype": "Delivery Note",
				"field_map": {
					"name": "delivery_order",
					"posting_date": "posting_date",
					"posting_time": "posting_time"
				},
				"validation": {
					"docstatus": ["=", 1]
				}
			},
			"Delivery Order Item": {
				"doctype": "Delivery Note Item",
				"field_map": {
					"name": "delivery_order_item",
					"parent": "delivery_order",
					"against_sales_order": "against_sales_order",
					"so_detail": "so_detail"
				},
				"postprocess": update_item
			}
		},
		target_doc,
		set_missing_values
	)
	
	return doclist


@frappe.whitelist()
def get_transporter_list(delivery_order):
	"""
	Mendapatkan list transporter dari Delivery Order
	untuk ditampilkan di dialog
	"""
	transporters = frappe.get_all(
		"Delivery Order Transporter",
		filters={"parent": delivery_order},
		fields=[
			"name",
			"transporter",
			"transporter_name", 
			"vehicle_no",
			"driver_name",
			"driver_contact",
			"lr_no",
			"lr_date"
		]
	)
	
	return transporters