# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import get_last_day, add_months, getdate, now_datetime
from datetime import datetime, timedelta, time

class MonthlyCPOMovement(Document):
	def on_submit(self):
		if not self.perbedaan or self.perbedaan == 0:
			return

		posting_date = getdate(self.tanggal_akhir_bulan)
		posting_time = "23:59:59"

		sr = frappe.new_doc("Stock Reconciliation")
		sr.purpose = "Stock Reconciliation"
		sr.posting_date = posting_date
		sr.posting_time = posting_time
		sr.company = self.company
		sr.difference_account = self.akun_cogs
		sr.set_posting_time = 1  

		qty_stock = frappe.utils.flt(self.qty_stock)
		stock_adjustment = frappe.utils.flt(self.stock_adjustment)
		qty_final = qty_stock + stock_adjustment

		if not qty_final:
			return

		valuation_rate = frappe.utils.flt(self.balance_stock_setelah_cost_per_unit) / qty_final

		sr.append("items", {
			"item_code": self.master_barang,
			"warehouse": self.warehouse,
			"qty": qty_final,
			"valuation_rate": valuation_rate,
		})

		sr.insert(ignore_permissions=True)
		sr.submit()

		frappe.db.set_value(
			"Monthly CPO Movement",
			self.name,
			"stock_reconciliation", 
			sr.name
		)

		frappe.msgprint(
			f"Stock Reconciliation <b>{sr.name}</b> berhasil dibuat.",
			indicator="green",
			alert=True
		)

	def on_cancel(self):
		if self.stock_reconciliation:
			sr = frappe.get_doc("Stock Reconciliation", self.stock_reconciliation)
			if sr.docstatus == 1:
				sr.cancel()
			frappe.msgprint(
				f"Stock Reconciliation <b>{sr.name}</b> dibatalkan.",
				indicator="orange",
				alert=True
			)

	def validate(self):
		self.validate_duplicate()

	def validate_duplicate(self):
		existing = frappe.db.exists("Monthly CPO Movement", {
			"item": self.item,
			"warehouse": self.warehouse,
			"tanggal_akhir_bulan": self.tanggal_akhir_bulan,
			"name": ("!=", self.name),
			"docstatus": ("!=", 2)  # exclude cancelled
		})

		if existing:
			frappe.throw(
				f"Kombinasi Item <b>{self.item}</b>, Warehouse <b>{self.warehouse}</b>, "
				f"dan Tanggal <b>{self.tanggal_akhir_bulan}</b> sudah ada di dokumen "
				f"<b><a href='/app/monthly-cpo-movement/{existing}'>{existing}</a></b>.",
				title="Duplikat Tidak Diizinkan"
			)

@frappe.whitelist()
def get_cpo_movement_data(item_code, warehouse, tanggal_akhir_bulan, cost_per_unit_produced):
	if not item_code or not warehouse or not tanggal_akhir_bulan:
		return {}

	current_date = getdate(tanggal_akhir_bulan)
	prev_month_end = get_last_day(add_months(current_date, -1))
	
	bulan_start = prev_month_end + timedelta(days=1) 
	bulan_end = current_date

	total_value_erp = 0

	cost_per_unit_processed = frappe.utils.flt(cost_per_unit_produced)

	sle_prev = frappe.db.sql("""
		SELECT qty_after_transaction, stock_value
		FROM `tabStock Ledger Entry`
		WHERE 
			item_code = %(item_code)s
			AND warehouse = %(warehouse)s
			AND posting_date <= %(prev_month_end)s
			AND is_cancelled = 0

		ORDER BY posting_date DESC, posting_time DESC, creation DESC
		LIMIT 1
	""", {
		'item_code': item_code,
		'warehouse': warehouse,
		'prev_month_end': prev_month_end
	}, as_dict=True)

	qty_akhir_bulan_lalu = sle_prev[0].qty_after_transaction if sle_prev else 0
	balance_akhir_bulan_lalu = sle_prev[0].stock_value if sle_prev else 0
	total_value_erp =+ balance_akhir_bulan_lalu

	sle_masuk_list = frappe.db.sql("""
		SELECT 
			sle.actual_qty,
			sle.stock_value_difference,
			sle.voucher_type
		FROM `tabStock Ledger Entry` sle
		WHERE 
			sle.item_code = %(item_code)s
			AND sle.warehouse = %(warehouse)s
			AND sle.posting_date BETWEEN %(bulan_start)s AND %(bulan_end)s
			AND sle.actual_qty > 0
			AND sle.is_cancelled = 0
	""", {
		'item_code': item_code,
		'warehouse': warehouse,
		'bulan_start': bulan_start,
		'bulan_end': bulan_end
	}, as_dict=True)

	total_qty_masuk = 0
	total_value_masuk = 0

	for sle in sle_masuk_list:
		qty = frappe.utils.flt(sle.actual_qty)
		total_qty_masuk += qty
		total_value_erp += frappe.utils.flt(sle.stock_value_difference)

		if sle.voucher_type == 'Stock Entry':
			total_value_masuk += qty * cost_per_unit_processed
		else:
			total_value_masuk += frappe.utils.flt(sle.stock_value_difference)

	total_qty_masuk += qty_akhir_bulan_lalu
	total_value_masuk += balance_akhir_bulan_lalu

	cost_per_unit_sold = (total_value_masuk / total_qty_masuk) if total_qty_masuk else 0

	sle_keluar = frappe.db.sql("""
		SELECT SUM(ABS(actual_qty)) AS total_qty_keluar, SUM(ABS(stock_value_difference)) as total_value_keluar
		FROM `tabStock Ledger Entry`
		WHERE 
			item_code = %(item_code)s
			AND warehouse = %(warehouse)s
			AND posting_date BETWEEN %(bulan_start)s AND %(bulan_end)s
			AND actual_qty < 0
			AND is_cancelled = 0
	""", {
		'item_code': item_code,
		'warehouse': warehouse,
		'bulan_start': bulan_start,
		'bulan_end': bulan_end
	}, as_dict=True)

	total_qty_keluar = frappe.utils.flt(sle_keluar[0].total_qty_keluar) if sle_keluar else 0
	total_value_keluar = round(total_qty_keluar * cost_per_unit_sold)
	total_value_erp -= frappe.utils.flt(sle_keluar[0].total_value_keluar) if sle_keluar else 0

	return {
		'qty_akhir_bulan_lalu':    qty_akhir_bulan_lalu,
		'balance_akhir_bulan_lalu': balance_akhir_bulan_lalu,
		'total_qty_masuk':         total_qty_masuk,
		'total_value_masuk':       total_value_masuk,
		'cost_per_unit_sold':      cost_per_unit_sold,
		'total_qty_keluar':        total_qty_keluar,
		'total_value_keluar':      total_value_keluar,
		'qty_stock':			   total_qty_masuk - total_qty_keluar,
		'balance_stock':		   total_value_erp,
		'balance_stock_setelah_cost_per_unit': total_value_masuk - total_value_keluar,
		'perbedaan':			   total_value_masuk - total_value_keluar - total_value_erp
	}