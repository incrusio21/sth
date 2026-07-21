# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, format_date, get_link_to_form
from frappe.query_builder.functions import Coalesce, Sum

from sth.controllers.buku_kerja_mandor import BukuKerjaMandorController
from frappe import _

class BukuKerjaMandorPanen(BukuKerjaMandorController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.plantation_setting_def.extend([
			["salary_component", "bkm_panen_component"],
			["denda_salary_component", "denda_sc"],
			["brondolan_salary_component", "brondolan_sc"],
			["kontanan_salary_component", "premi_kontanan_component"],
		])

		self.fieldname_total.extend([
			"jumlah_janjang", "qty_brondolan", "brondolan_amount", "denda", "kontanan_amount"
		])

		self.kegiatan_fetch_fieldname.extend(["upah_brondolan", "premi_kontanan_basis"])

		self.payment_log_updater.extend([
			{
				"target_amount": "kontanan_amount",
				"target_salary_component": "kontanan_salary_component",
				"component_type": "Kontanan",
				"removed_if_zero": True
			},
			{
				"target_amount": "denda",
				"target_salary_component": "denda_salary_component",
				"component_type": "Denda",
				"removed_if_zero": True
			},
			{
				"target_amount": "brondolan_amount",
				"target_salary_component": "brondolan_salary_component",
				"component_type": "Brondolan",
				"removed_if_zero": True
			}
		])

		self._clear_fields = ["blok"]
		self._mandor_dict.extend([
			{"fieldname": "mandor1"},
			{"fieldname": "kerani_panen"},
		])
		self._bkm_name = "Panen"

	def validate(self):
		self.isi_cost_center()
		if self.trans_no:
			trans_no = self.trans_no
			karyawan = self.hasil_kerja[0].employee
			blok = self.hasil_kerja[0].blok

			duplikat = frappe.db.sql("""
				SELECT bkmp.name
				FROM `tabBuku Kerja Mandor Panen` bkmp
				INNER JOIN `tabDetail BKM Hasil Kerja Panen` hk ON hk.parent = bkmp.name
				WHERE bkmp.trans_no = %s
					AND hk.employee = %s
					AND hk.blok = %s
					AND bkmp.name != %s
				LIMIT 1
			""", (trans_no, karyawan, blok, self.name))

			if duplikat:
				frappe.throw(
					f"Data sudah ada dengan Trans No <b>{trans_no}</b>, "
					f"Karyawan <b>{karyawan}</b>, dan Blok <b>{blok}</b>. "
					f"Referensi: {duplikat[0][0]}"
				)


		self.reset_automated_data()
		
		super().validate()
	
	def isi_cost_center(self):
		self.cost_center = "{} - {}".format(self.hasil_kerja[0].blok, frappe.get_doc("Company",self.company).abbr)
		self.db_update()
		frappe.db.commit()

	def reset_automated_data(self):
		self.transfered_janjang = self.transfered_brondolan = \
		self.netto_weight = self.weight_total = self.bjr = 0

	def set_payroll_date(self):
		if not self.is_kontanan:
			super().set_payroll_date()
		else:
			self.payroll_date, self.against_salary_component = frappe.db.get_value("Pengajuan Panen Kontanan", {
				"bkm_panen": self.name, "docstatus": 1
			}, ["posting_date", "against_kontanan_component"]) or ["", ""]

	def on_submit(self):
		super().on_submit()
		self.create_recap_panen_by_blok()
		# self.make_gl_entries()

	def on_cancel(self):
		super().on_cancel()
		self.cancel_gl_entries()

	def make_gl_entries(self, method=None):
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

		if self.grand_total:

			gl_entries.append(
				frappe.get_doc({
					"doctype": "GL Entry",
					"posting_date": self.posting_date,
					"account": akun_debit,
					"debit": self.grand_total,
					"credit": 0.0,
					"debit_in_account_currency": self.grand_total,
					"credit_in_account_currency": 0.0,
					"voucher_type": self.doctype,
					"voucher_no": self.name,
					"company": self.company,
					"remarks": f"BKM Panen - {self.name}",
					"cost_center": self.cost_center
				})
			)

			# --- CREDIT ---
			gl_entries.append(
				frappe.get_doc({
					"doctype": "GL Entry",
					"posting_date": self.posting_date,
					"account": akun_kredit,
					"debit": 0.0,
					"credit": self.grand_total,
					"debit_in_account_currency": 0.0,
					"credit_in_account_currency": self.grand_total,
					"voucher_type": self.doctype,
					"voucher_no": self.name,
					"company": self.company,
					"remarks": f"BKM Panen - {self.name}",
					"cost_center": self.cost_center
				})
			)

		# Simpan semua GL Entry
		for gl in gl_entries:
			gl.flags.ignore_permissions = True
			gl.insert()

		frappe.msgprint(_("GL Entry berhasil dibuat."), indicator="green", alert=True)

	def cancel_gl_entries(doc, method=None):
		"""
		Batalkan (reverse) GL Entry saat dokumen di-cancel.
		"""
		frappe.db.sql(
			"""
			UPDATE `tabGL Entry`
			SET is_cancelled = 1
			WHERE voucher_type = %s
			  AND voucher_no   = %s
			  AND is_cancelled = 0
			""",
			(doc.doctype, doc.name),
		)
		frappe.msgprint(_("GL Entry berhasil dibatalkan."), indicator="orange", alert=True)

	def create_recap_panen_by_blok(self):
		blok_dict = {}
		for hk in self.hasil_kerja:
			blok = blok_dict.setdefault(hk.blok, {
				"voucher_type": self.doctype, 
				"voucher_no": self.name,
				"company": self.company,
				"posting_date": self.posting_date,
				"jumlah_janjang": 0,
				"jumlah_brondolan": 0,
				"kontanan": self.is_kontanan
			})

			blok["jumlah_janjang"] += hk.jumlah_janjang
			blok["jumlah_brondolan"] += hk.qty_brondolan
		
		message = ""
		for b, value in blok_dict.items():
			rekap_panen = "create_rekap_panen"
			try:
				frappe.db.savepoint(rekap_panen)
				rpb = frappe.new_doc("Recap Panen by Blok")
				rpb.blok = b
				rpb.update(value)
				rpb.save()
			except frappe.UniqueValidationError:
				if frappe.message_log:
					frappe.message_log.pop()
					
				frappe.db.rollback(save_point=rekap_panen)  # preserve transaction in postgres
				message += f"<br>{b}"

		if message:
			frappe.throw(f"List Blok already used in {format_date(self.posting_date)}: {message}")

	def delete_recap_panen(self):
		for epl in frappe.get_all(
			"Recap Panen by Blok", 
			filters={"voucher_type": self.doctype, "voucher_no": self.name}, 
			pluck="name"
		):
			frappe.delete_doc("Recap Panen by Blok", epl, flags=frappe._dict(transaction_panen=True))
		
	def update_rate_or_qty_value(self, item, precision):
		if item.parentfield != "hasil_kerja":
			return
		
		item.qty = flt((item.bjr or 0) * item.jumlah_janjang)
		item.rate = item.get("rate") or self.rupiah_basis
		item.brondolan = flt(self.upah_brondolan)
		item.status = "Pending" if not item.bjr else "Approved"

		if not self.manual_hk:
			item.hari_kerja = min(flt(item.qty / self.volume_basis), 1)

	def update_value_after_amount(self, item, precision):
		# Hitung total brondolan
		item.brondolan_amount = flt(item.brondolan * flt(item.qty_brondolan), precision)
		item.kontanan_amount = flt(item.qty * flt(self.premi_kontanan_basis), precision) if self.is_kontanan else 0

		# Perhitungan denda
		factors = [ 
			"buah_tidak_dipanen", "buah_mentah_disimpan", "buah_mentah_ditinggal",
			"brondolan_tinggal", "pelepah_tidak_disusun","tangkai_panjang",
			"buah_tidak_disusun", "pelepah_sengkleh"
		]

		# Hitung total denda dengan menjumlahkan rate * nilai item
		item.denda = sum(flt(item.get(field)) * flt(self.get(f"{field}_rate")) for field in factors)

		item.sub_total = flt(item.amount + item.brondolan_amount + item.kontanan_amount, precision)

	def after_calculate_grand_total(self):
		self.grand_total -= self.hasil_kerja_denda 

	def update_kontanan_used(self, cancel=0):
		self.set_payroll_date()
		self.is_rekap = not cancel
		self.db_update()
		
		self.create_or_update_payment_log()

	def update_hasil_kerja_bjr(self, block_dict=None):
		# update bjr untuk menentukan nilai upah pegawai
		update_payment_log = []
		for hk in self.hasil_kerja:
			if block_dict and not block_dict.get(hk.blok):
				continue
			
			hk.bjr = block_dict[hk.blok]
			update_payment_log.append(hk.name)

		self.calculate()
		self.db_update_all()
		
		if self.is_kontanan and self.is_rekap:
			frappe.throw(f"Document already have Pengajuan Kontanan. please cancel it first")

		self.create_or_update_payment_log(update_payment_log, "Upah")
		self.create_or_update_mandor_premi()
		self.make_gl_entries()

