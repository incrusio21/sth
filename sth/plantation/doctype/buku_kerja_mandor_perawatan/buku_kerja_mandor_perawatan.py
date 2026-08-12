# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt
from sth.controllers.buku_kerja_mandor import BukuKerjaMandorController
from sth.custom.api import fix_kegiatan_from_api, fix_mandor_from_api, submit_after_insert

class BukuKerjaMandorPerawatan(BukuKerjaMandorController):
	# draft ikut dihitung ulang oleh tombol Re-calculate Premi
	# repair_include_draft = True

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.plantation_setting_def.extend([
			["salary_component", "bkm_perawatan_component"],
			["premi_salary_component", "premi_sc"],
		])
		
		self.fieldname_total.extend(["premi_amount"])

		self.kegiatan_fetch_fieldname.extend(["min_basis_premi", "rupiah_premi"])

		self.payment_log_updater.extend([
			{
				"target_amount": "premi_amount",
				"target_salary_component": "premi_salary_component",
                "component_type": "Premi",
				"removed_if_zero": True
			}
		])

		self._mandor_dict = []

	def before_insert(self):
		fix_mandor_from_api(self)
		fix_kegiatan_from_api(self)

		# Data dari API kadang masuk dengan docstatus=1 langsung, sehingga
		# proses insert tidak pernah melewati siklus submit (on_submit tidak jalan).
		# Di sini docstatus dipaksa jadi draft dulu, lalu submit() dipanggil manual
		# di after_insert supaya validate/before_submit/on_submit tetap dieksekusi.
		if self.docstatus == 1:
			self.flags.submit_after_insert = True
			self.docstatus = 0

	def after_insert(self):
		if self.flags.get("submit_after_insert"):
			submit_after_insert(self)

	def validate(self):
		if self.trans_no:
			trans_no = self.trans_no
			karyawan = self.hasil_kerja[0].employee

			duplikat = frappe.db.sql("""
				SELECT bkmp.name
				FROM `tabBuku Kerja Mandor Perawatan` bkmp
				INNER JOIN `tabDetail BKM Hasil Kerja Perawatan` hk ON hk.parent = bkmp.name
				WHERE bkmp.trans_no = %s
					AND hk.employee = %s
					AND bkmp.name != %s
				LIMIT 1
			""", (trans_no, karyawan, self.name))

			if duplikat:
				frappe.throw(
					f"Data sudah ada dengan Trans No <b>{trans_no}</b>, "
					f"Karyawan <b>{karyawan}</b>. "
					f"Referensi: {duplikat[0][0]}"
				)

		self.validate_hasil_kerja_harian()
		super().validate()


	def get_cost_center(self):
		"""Cost center dokumen ini: dari batch, blok, atau tahun tanam sesuai kategori.

		Satu tempat untuk dua pemakai — GL Entry dan Stock Entry material — supaya
		biaya upah dan biaya materialnya tidak bisa jatuh ke cost center berbeda.

		Balikan "" kalau sumbernya belum terisi. make_gl_entry memang tidak membuat
		jurnal untuk keadaan itu, dan Stock Entry dibiarkan memakai default company.
		"""
		abbr = frappe.get_cached_value("Company", self.company, "abbr")

		if self.kategori_kegiatan == "BBT":
			return "{} - {}".format(self.batch, abbr) if self.batch else ""

		if self.kategori_kegiatan == "TM":
			deskripsi = frappe.get_cached_value("Blok", self.blok, "deskripsi") if self.blok else None
			return "{} - {}".format(deskripsi, abbr) if deskripsi else ""

		if self.kategori_kegiatan == "TBM":
			return "{} - {}".format(self.tahun_tanam, abbr) if self.tahun_tanam else ""

		return ""

	def validate_hasil_kerja_harian(self):
		if self.get("is_bibitan"):
			return
		
		if self.uom == "HA" and self.hasil_kerja_qty > self.luas_blok:
			frappe.throw("Hasil Kerja exceeds Luas Blok")

	def calculate(self):
		# have_premi diisi lewat fetch_from, yang hanya jalan saat save(). re-calculate
		# memakai db_update_all sehingga nilainya perlu diambil ulang dari master Kegiatan.
		if self.flags.re_calculate and self.kegiatan:
			self.have_premi = frappe.get_cached_value("Kegiatan", self.kegiatan, "have_premi")

		super().calculate()

	def update_rate_or_qty_value(self, item, precision):
		if item.parentfield != "hasil_kerja":
			return
		
		# saat re-calculate, upah diambil ulang dari master kegiatan supaya perubahan
		# rupiah_basis ikut terpakai. penyimpanan biasa tetap menghormati input manual.
		if self.flags.re_calculate and self.rupiah_basis:
			item.rate = self.rupiah_basis
		else:
			item.rate = item.get("rate") or self.rupiah_basis

		item.premi_amount = 0

		if not self.manual_hk:
			item.hari_kerja = min(flt(item.qty / (self.volume_basis or 1)), 1)
		
		if self.have_premi and item.qty >= self.min_basis_premi:
			item.premi_amount = self.rupiah_premi

	def update_value_after_amount(self, item, precision):
		if item.parentfield != "hasil_kerja":
			return
		
		# Hitung total brondolan
		item.sub_total = flt(item.amount + item.premi_amount, precision)
		
	def on_submit(self, update_realization=True):

		super().on_submit(update_realization=False)
		if not self.material:
			pass
			# self.update_rkb_realization()
		else:
			self.create_ste_issue()

		# GL Entry baru dibuat saat dokumen Posted, lihat BukuKerjaMandorController
		self.make_gl_entry_on_submit()

	def create_ste_issue(self):
		ste = frappe.new_doc("Stock Entry")
		ste.company = self.company
		ste.stock_entry_type = "Material Used"
		ste.posting_date = self.posting_date
		ste.set_purpose_for_stock_entry()
		account_kegiatan = ""
		if self.kegiatan_account:
			account_kegiatan = self.kegiatan_account
		else:
			frappe.throw("Account Kegiatan tidak boleh kosong.")

		ada_item = 0

		# Cost center dibawa ke baris Stock Entry, bukan ke headernya: di ERPNext
		# cost_center memang milik Stock Entry Detail dan itu yang dipakai saat
		# menjurnal expense_account.
		cost_center = self.get_cost_center()

		for d in self.material:
			if d.item:
				ada_item = 1

			item = {
				"s_warehouse": d.warehouse,
				"item_code": d.item,
				"qty": d.qty,
				"expense_account": account_kegiatan
			}

			# kalau kosong, biarkan ERPNext memakai default company seperti sebelumnya
			if cost_center:
				item["cost_center"] = cost_center

			ste.append("items", item)
		if ada_item == 1:
			ste.submit()
			self.stock_entry = ste.name
			for index, item in enumerate(ste.items):
				self.material[index].update({
					"stock_entry_detail": item.name,
					"rate": item.basic_rate,
				})

			self.set_material_rate(get_valuation_rate=False)

	def set_material_rate(self, get_valuation_rate=True):
		if get_valuation_rate:
			for d in self.material:
				d.rate = frappe.get_value("Stock Entry Detail", d.stock_entry_detail, "basic_rate")
				
		self.calculate_item_table_values()
		self.calculate_grand_total()

		self.db_update_all()

		# self.update_rkb_realization()

	def on_cancel(self):
		self.delete_ste()

		super().on_cancel()
		self.make_reverse_gl_entry()

	def delete_ste(self):
		if not self.stock_entry:
			return
			
		ste = frappe.get_doc("Stock Entry", self.stock_entry)
		if ste.docstatus == 1:
			ste.cancel()

		self.db_set("stock_entry", "")

		ste.delete()

	def get_nilai_gl_entry(self):
		"""Nilai jurnal BKM: upah dan preminya saja, tanpa material.

		Bukan grand_total. Material sudah dijurnal Stock Entry "Material Used" ke
		akun kegiatan yang sama, sedangkan calculate_grand_total menjumlahkan semua
		field ber-"amount" termasuk material_amount — memakai grand_total membuat
		akun kegiatan terdebit dua kali sebesar nilai materialnya.
		"""
		return flt(self.hasil_kerja_amount) + flt(self.hasil_kerja_premi_amount)

	def make_gl_entry(self, method=None):
		gl_entries = []
		akun_debit = self.kegiatan_account
		akun_kredit = ""

		single_doc = frappe.get_single("Plantation Settings")
		for row in single_doc.plantation_settings_akun_kredit_bkm:
			if row.company == self.company:
				akun_kredit = row.account

		if not akun_kredit:
			frappe.throw(
				_("Account Kredit BKM untuk company <b>{0}</b> tidak ditemukan. "
				  "Pastikan akun tersebut sudah dipasang di Plantation Settings").format(self.company)
			)

		cost_center = self.get_cost_center()
		nilai = self.get_nilai_gl_entry()

		if nilai and cost_center:

			gl_entries.append(
				frappe.get_doc({
					"doctype": "GL Entry",
					"posting_date": self.posting_date,
					"account": akun_debit,
					"debit": nilai,
					"credit": 0.0,
					"debit_in_account_currency": nilai,
					"credit_in_account_currency": 0.0,
					"voucher_type": self.doctype,
					"voucher_no": self.name,
					"company": self.company,
					"remarks": f"BKM Perawatan - {self.name}",
					"cost_center": cost_center
				})
			)

			# --- CREDIT ---
			gl_entries.append(
				frappe.get_doc({
					"doctype": "GL Entry",
					"posting_date": self.posting_date,
					"account": akun_kredit,
					"debit": 0.0,
					"credit": nilai,
					"debit_in_account_currency": 0.0,
					"credit_in_account_currency": nilai,
					"voucher_type": self.doctype,
					"voucher_no": self.name,
					"company": self.company,
					"remarks": f"BKM Perawatan - {self.name}",
					"cost_center": cost_center
				})
			)

		# Simpan semua GL Entry
		for gl in gl_entries:
			gl.flags.ignore_permissions = True
			gl.insert()

		self.show_gl_alert(_("GL Entry berhasil dibuat."))

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