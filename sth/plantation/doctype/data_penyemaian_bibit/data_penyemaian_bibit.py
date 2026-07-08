# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
from frappe.query_builder.functions import Sum

from sth.controllers.status_updater import StatusUpdater
from frappe import _
class DataPenyemaianBibit(StatusUpdater):
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.status_updater = [
			{
				"target_dt": "Pengeluaran Barang Item",
				"join_field": "pengeluaran_barang_item",
				"target_field": "penyemaian_qty",
				"target_parent_dt": "Pengeluaran Barang",
				"target_parent_field": "per_penyemaian",
				"target_ref_field": "qty_penyemaian",
				"source_field": "qty_planting",
				"percent_join_field_parent": "voucher_no",
				"no_allowance": True,
				"is_child": False
			},
		]

	
	def validate(self):
		self.check_missing_value()
		# self.limit_qty()
		self.calculate_grand_total_qty()
	
	def check_missing_value(self):
		# if not self.item_code or not self.batch:
		# 	frappe.throw(f"Item Code, Batch cant be empty.")

		if not self.qty_planting:
			frappe.throw(f"Qty Planting cant be zero.")

	def limit_qty(self):
		if self.qty_planting < self.qty_before_afkir:
			frappe.throw(f"Qty Seed Afkir cant be greather than Qty Planting.")

	def calculate_amount_from_pengeluaran_barang(self):
		if not self.voucher_no or not self.item_code:
			return

		ste_name = frappe.db.get_value(
			"Stock Entry",
			{"pengeluaran_barang": self.voucher_no, "docstatus": 1},
			"name"
		)
		if not ste_name:
			return

		# Ambil valuation_rate dari baris Stock Entry yang cocok
		sed = frappe.qb.DocType("Stock Entry Detail")
		result = (
			frappe.qb.from_(sed)
			.select(sed.valuation_rate)
			.where(
				(sed.parent == ste_name)
				& (sed.item_code == self.item_code)
			)
			.limit(1)
		).run()

		valuation_rate = flt(result[0][0]) if result and result[0][0] else 0.0
		self.amount = flt(self.qty_planting * valuation_rate)

	def calculate_grand_total_qty(self):
		self.calculate_qty_dobletone_and_afkir()
		self.calculate_amount_from_pengeluaran_barang()

		self.qty = flt(self.qty_planting + self.qty_dobletone - self.qty_after_afkir)

	def calculate_qty_dobletone_and_afkir(self):
		dpda = frappe.qb.DocType("Data Pencatatan Dobletone Dan Afkir")

		def get_total(pencatatan_type):
			return (
				frappe.qb.from_(dpda)
				.select(Sum(dpda.qty))
				.where(
					(dpda.data_penyemaian_bibit == self.name)
					& (dpda.item_code == self.item_code)
					& (dpda.batch == self.batch)					
					& (dpda.docstatus == 1)
					& (dpda.data_pencatatan_type == pencatatan_type)
				)
			).run()[0][0] or 0.0

		self.qty_dobletone = get_total("Dobletone")
		self.qty_after_afkir = get_total("Afkir")

	def on_submit(self):
		self.make_gl_entry()
		self.make_batch()

		self.update_penyemaian_qty()
		# self.update_prevdoc_status()
		# self.make_ste_issue()

	def make_batch(self):
		if not frappe.db.exists("Batch Bibit", {"batch_id": self.batch, "item_code": self.item_code}):
			batch_doc = frappe.new_doc("Batch Bibit")
			batch_doc.batch_id = self.batch
			batch_doc.item_code = self.item_code
			batch_doc.save()
		self.make_cost_center()

	def make_cost_center(self):
		if frappe.db.exists("Cost Center", {"cost_center_name": self.batch, "company": self.company}):
			return

		company_doc = frappe.get_doc("Company", self.company)
		parent_cost_center = f"Batch Bibit - {company_doc.abbr}"

		cc = frappe.new_doc("Cost Center")
		cc.cost_center_name = self.batch
		cc.parent_cost_center = parent_cost_center
		cc.company = self.company
		cc.is_group = 0
		cc.flags.ignore_permissions = True
		cc.insert()
		frappe.db.commit()

	def make_ste_issue(self):		
		doc = frappe.new_doc("Stock Entry")
		doc.stock_entry_type = 'Material Issue'
		doc.company = self.company

		doc.set_posting_time = 1
		doc.posting_date = self.posting_date
		doc.posting_time = self.posting_time
		
		akun_expense = ""
		plantation_settings = frappe.get_single("Plantation Settings")
		
		for row in plantation_settings.akun_kredit_penyemaian_bibit:
			if row.company == self.company:
				akun_expense = row.account

		warehouse = frappe.db.get_value(
			"Pengeluaran Barang Item",
			{
				"parent": self.voucher_no,
				"kode_barang": self.item_code,
				"batch_no": self.batch
			},
			"warehouse"
		)
		doc.from_warehouse = warehouse

		doc.append("items", {			
			"item_code": self.item_code,
			"qty": self.qty,
			"use_serial_batch_fields": 1,
			"batch_no": self.batch,
			"expense_account": akun_expense
		})
		
		doc.submit()

		self.db_set("stock_entry", doc.name)
		self.db_set("amount", doc.total_outgoing_value)

	def on_cancel(self):

		self.update_penyemaian_qty(is_cancel=True)
		self.make_reverse_gl_entry()
		# self.update_prevdoc_status()
		# self.cancel_or_remove_ste()

	def on_trash(self):

		if self.docstatus == 2:
			self.delete_gl_entry()


	def delete_gl_entry(self):

		frappe.db.delete(
			"GL Entry",
			{
				"voucher_type": self.doctype,
				"voucher_no": self.name
			}
		)

	def after_delete(self):
		self.cancel_or_remove_ste(delete=1)

	def cancel_or_remove_ste(self, delete=0):
		if not self.stock_entry:
			return
		
		doc = frappe.get_doc("Stock Entry", self.stock_entry)
		if doc.docstatus == 1:
			doc.cancel()
		
		if delete:
			doc.delete()

	def get_batch_cost_center(self):
		name = frappe.db.get_value(
			"Cost Center",
			{"cost_center_name": self.batch, "company": self.company},
			"name"
		)
		return name or frappe.get_doc("Company", self.company).cost_center

	def make_gl_entry(self, method=None):
		gl_entries = []
		cost_center = self.get_batch_cost_center()

		# ste_name = frappe.db.get_value(
		# 	"Stock Entry",
		# 	{"pengeluaran_barang": self.voucher_no, "docstatus": 1},
		# 	"name"
		# )

		# akun_kredit = ""
		# for row in frappe.get_doc("Stock Entry",ste_name).items:
		# 	akun_kredit = row.expense_account

		# akun_debit = ""
		# plantation_settings = frappe.get_single("Plantation Settings")
	
		# for row in plantation_settings.akun_kredit_penyemaian_bibit:
		# 	if row.company == self.company:
		# 		akun_debit = row.account

		# if not akun_debit:
		# 	frappe.throw(
		# 		_("Account Penyemaian untuk company <b>{0}</b> tidak ditemukan. "
		# 		  "Pastikan akun tersebut sudah dipasang di Plantation Settings").format(self.company)
		# 	)

		gl_entries.append(
			frappe.get_doc({
				"doctype": "GL Entry",
				"posting_date": self.posting_date,
				"account": self.debit_account,
				"debit": self.amount,
				"credit": 0.0,
				"debit_in_account_currency": self.amount,
				"credit_in_account_currency": 0.0,
				"voucher_type": self.doctype,
				"voucher_no": self.name,
				"company": self.company,
				"remarks": f"Penyemaian Bibit - {self.name}",
				"cost_center": cost_center
			})
		)

		# --- CREDIT ---
		gl_entries.append(
			frappe.get_doc({
				"doctype": "GL Entry",
				"posting_date": self.posting_date,
				"account": self.credit_account,
				"debit": 0.0,
				"credit": self.amount,
				"debit_in_account_currency": 0.0,
				"credit_in_account_currency": self.amount,
				"voucher_type": self.doctype,
				"voucher_no": self.name,
				"company": self.company,
				"remarks": f"Penyemaian Bibit - {self.name}",
				"cost_center": cost_center
			})
		)

		# Simpan semua GL Entry
		for gl in gl_entries:
			gl.flags.ignore_permissions = True
			gl.insert()

		frappe.msgprint(_("GL Entry berhasil dibuat."), indicator="green", alert=True)

	def make_reverse_gl_entry(self, method=None):
		"""
		Buat GL Entry pembalik (reverse) dengan membalik debit/credit dari entry asli.
		"""
		original_entries = frappe.get_all(
			"GL Entry",
			filters={
				"voucher_type": self.doctype,
				"voucher_no": self.name,
				"is_cancelled": 0
			},
			fields=[
				"account", "debit", "credit",
				"debit_in_account_currency", "credit_in_account_currency",
				"cost_center", "remarks", "company"
			]
		)

		if not original_entries:
			return

		for entry in original_entries:
			reverse_gl = frappe.get_doc({
				"doctype": "GL Entry",
				"posting_date": self.posting_date,
				"account": entry.account,
				"debit": entry.credit,
				"credit": entry.debit,
				"debit_in_account_currency": entry.credit_in_account_currency,
				"credit_in_account_currency": entry.debit_in_account_currency,
				"voucher_type": self.doctype,
				"voucher_no": self.name,
				"company": entry.company,
				"remarks": f"Reverse: {entry.remarks}",
				"cost_center": entry.cost_center,
			})
			reverse_gl.flags.ignore_permissions = True
			reverse_gl.insert()

		frappe.db.sql(
			"""
			UPDATE `tabGL Entry`
			SET is_cancelled = 1
			WHERE voucher_type = %s
			  AND voucher_no   = %s
			  AND is_cancelled = 0
			""",
			(self.doctype, self.name),
		)

		frappe.msgprint(_("GL Entry berhasil di-reverse."), indicator="orange", alert=True)

	def update_penyemaian_qty(self, is_cancel=False):

		if not self.voucher_no:
			return

		qty = flt(self.qty_planting)

		if is_cancel:
			qty = -qty

		item = frappe.get_doc(
			"Pengeluaran Barang Item",
			self.pengeluaran_barang_item
		)

		item.penyemaian_qty = flt(item.penyemaian_qty) + qty
		item.save(ignore_permissions=True)

# @frappe.whitelist()
# def select_pengeluaran_barang_item(voucher_no):
# 	prec = frappe.qb.DocType("Pengeluaran Barang Item")
# 	item = frappe.qb.DocType("Item")

# 	return (
# 		frappe.qb.from_(prec)
# 		.left_join(item).on(item.name == prec.kode_barang)
# 		.select(
# 			prec.name.as_("detail_name"),
# 			prec.kode_barang,
# 			item.item_name,
# 			prec.jumlah
# 		)
# 		.where(prec.parent == voucher_no)
# 	).run(as_dict=1)

@frappe.whitelist()
def select_pengeluaran_barang_item(voucher_no):
	prec = frappe.qb.DocType("Pengeluaran Barang Item")
	item = frappe.qb.DocType("Item")

	return (
		frappe.qb.from_(prec)
		.left_join(item).on(item.name == prec.kode_barang)
		.select(
			prec.name.as_("detail_name"),
			prec.kode_barang,
			item.item_name,
			(prec.jumlah - prec.penyemaian_qty).as_("jumlah")
		)
		.where(
			(prec.parent == voucher_no)
			& ((prec.jumlah - prec.penyemaian_qty) > 0)
		)
	).run(as_dict=1)

@frappe.whitelist()
def get_akun_penyemaian(company):
	settings = frappe.get_single('Plantation Settings')

	debit = next(
		(r.account for r in settings.plantation_settings_akun_debit_penyemaian_bibit if r.company == company),
		None
	)
	kredit = next(
		(r.account for r in settings.plantation_settings_akun_kredit_penyemaian_bibit if r.company == company),
		None
	)

	return {'debit_account': debit, 'credit_account': kredit}


