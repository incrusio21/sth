# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.query_builder.functions import Sum
from frappe import _
from frappe.utils import flt


class DataPenanamanBibit(Document):
	def get_available_qty(self):
		data = frappe.get_value(
			"Data Penyemaian Bibit",
			self.data_penyemaian_bibit,
			["transplanting_qty", "planting_qty"],
			as_dict=True,
			for_update=True,
		)

		if data:
			self.available_qty = (data.get("transplanting_qty") or 0) - (data.get("planting_qty") or 0)
		else:
			self.available_qty = 0
	
	def limit_qty(self):
		if(self.available_qty < self.qty):
			frappe.throw(f"Jumlah Bibit must not be greater than Available Qty ({self.available_qty})")
   
		if(self.qty<0):
			frappe.throw(f"Jumlah Bibit must not be less than 0")

	def get_base_rupiah_basis(self):
		"""Harga dasar bibit per unit, diambil dari Data Penyemaian Bibit (bukan dari field rupiah_basis
		yang sekarang jadi field hasil hitungan total_jurnal / qty)."""
		if not self.data_penyemaian_bibit:
			return 0

		d = frappe.db.get_value(
			"Data Penyemaian Bibit", self.data_penyemaian_bibit, ["qty", "amount"], as_dict=True
		)
		if not d or not d.qty:
			return 0
		return flt(d.amount) / flt(d.qty)

	def calculate_totals(self):
		qty = flt(self.qty)
		basis = self.get_base_rupiah_basis()
		available_qty = flt(self.available_qty)
		total_bkm = flt(self.total_bkm)

		self.total_bibit = qty * basis

		self.actual_amount_bkm = 0
		if available_qty:
			self.actual_amount_bkm = (qty / available_qty) * total_bkm

		self.total_jurnal = self.total_bibit + self.actual_amount_bkm

		self.rupiah_basis = (self.total_jurnal / qty) if qty else 0
  
	def validate(self):
		# self.get_available_qty()
		if flt(self.qty) <= 0:
			frappe.throw("Qty harus lebih besar dari 0.")
		
		self.limit_qty()
		self.calculate_totals()

	def recalculate_qty_data_penyemaian_bibit(self):
		dpda = frappe.qb.DocType("Data Penanaman Bibit")

		def get_total():
			return (
				frappe.qb.from_(dpda)
				.select(Sum(dpda.qty))
				.where(
					(dpda.data_penyemaian_bibit == self.data_penyemaian_bibit)
					& (dpda.item_code == self.item_code)			
					& (dpda.docstatus == 1)
				)
			).run()[0][0] or 0.0

		used_total = get_total()		

		doc = frappe.get_doc("Data Penyemaian Bibit", self.data_penyemaian_bibit)
  
		doc.planting_qty = used_total
		doc.calculate_grand_total_qty()
		doc.db_update()

	def on_submit(self):
		self.make_gl_entry()
		self.recalculate_qty_data_penyemaian_bibit()
	
	def on_cancel(self):
		self.make_reverse_gl_entry()
		self.recalculate_qty_data_penyemaian_bibit()

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

	def get_cost_center_by_name(self, name):
		cc = frappe.db.get_value("Cost Center", {"cost_center_name": name, "company": self.company}, "name")
		if not cc:
			frappe.throw(_(f"Cost Center <b>{name}</b> untuk company <b>{self.company}</b> tidak ditemukan."))
		return cc

	def make_gl_entry(self, method=None):
		gl_entries = []

		tahun_tanam = frappe.db.get_value("Blok", self.blok, "tahun_tanam")
		if not tahun_tanam:
			frappe.throw(_(f"Tahun Tanam tidak ditemukan pada Blok <b>{self.blok}</b>."))

		debit_cost_center = self.get_cost_center_by_name(str(tahun_tanam))
		credit_cost_center = self.get_cost_center_by_name(self.batch)
		
		gl_entries.append(
			frappe.get_doc({
				"doctype": "GL Entry",
				"posting_date": self.posting_date,
				"account": self.debit_account,
				"debit": self.total_jurnal,
				"credit": 0.0,
				"debit_in_account_currency": self.total_jurnal,
				"credit_in_account_currency": 0.0,
				"voucher_type": self.doctype,
				"voucher_no": self.name,
				"company": self.company,
				"remarks": f"Penanaman Bibit - {self.name}",
				"cost_center": debit_cost_center
			})
		)

		# --- CREDIT ---
		gl_entries.append(
			frappe.get_doc({
				"doctype": "GL Entry",
				"posting_date": self.posting_date,
				"account": self.credit_account,
				"debit": 0.0,
				"credit": self.total_jurnal,
				"debit_in_account_currency": 0.0,
				"credit_in_account_currency": self.total_jurnal,
				"voucher_type": self.doctype,
				"voucher_no": self.name,
				"company": self.company,
				"remarks": f"Penanaman Bibit - {self.name}",
				"cost_center": credit_cost_center
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


@frappe.whitelist()
def get_rupiah_basis_by_batch(batch):
	bkm = frappe.db.get_all(
		'Buku Kerja Mandor Perawatan',
		filters={'batch': batch},
		fields=['grand_total']
	)
	return {
		'total_bkm': sum(r.grand_total or 0 for r in bkm)
	}
	
@frappe.whitelist()
def get_akun_penanaman(company):
	settings = frappe.get_single('Plantation Settings')

	debit = next(
		(r.account for r in settings.plantation_settings_akun_debit_penanaman_bibit if r.company == company),
		None
	)
	kredit = next(
		(r.account for r in settings.plantation_settings_akun_kredit_penanaman_bibit if r.company == company),
		None
	)

	return {'debit_account': debit, 'credit_account': kredit}

@frappe.whitelist()
def get_data_penyemaian(data_penyemaian_bibit):
	d = frappe.db.get_value(
		'Data Penyemaian Bibit',
		data_penyemaian_bibit,
		['qty', 'amount'],
		as_dict=True
	)

	# total_pemindahan = frappe.db.sql("""
	# 	SELECT COALESCE(SUM(qty), 0)
	# 	FROM `tabData Pemindahan Transplanting Bibit`
	# 	WHERE data_penyemaian_bibit = %s
	# 	AND docstatus = 1
	# """, (data_penyemaian_bibit,), as_list=True)[0][0]

	total_pemindahan = frappe.db.sql("""
		SELECT qty
		FROM `tabData Penyemaian Bibit`
		WHERE name = %s
		AND docstatus = 1
	""", (data_penyemaian_bibit,), as_list=True)[0][0]

	total_penanaman = frappe.db.sql("""
		SELECT COALESCE(SUM(qty), 0)
		FROM `tabData Penanaman Bibit`
		WHERE data_penyemaian_bibit = %s
		AND docstatus = 1
	""", (data_penyemaian_bibit,), as_list=True)[0][0]

	available_qty = flt(total_pemindahan) - flt(total_penanaman)

	rupiah_basis = (d.amount / d.qty) if d and d.qty else 0

	return {
		'qty': available_qty,
		'rupiah_basis': flt(rupiah_basis)
	}