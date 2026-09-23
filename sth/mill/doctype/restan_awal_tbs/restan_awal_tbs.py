# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import (
	EmptyStockReconciliationItemsError,
)
from erpnext.stock.utils import get_stock_balance

from sth.mill.doctype.data_tbs.data_tbs import get_warehouse_tbs

# Sebelum seluruh transaksi hari itu, termasuk Stock Entry Data TBS yang
# diposting pukul 23:59:59: yang ditetapkan saldo awal hari, bukan akhir hari.
WAKTU_REKONSILIASI = "00:00:00"


class RestanAwalTBS(Document):
	"""Patokan restan awal Data TBS satu unit sejak satu tanggal proses.

	Restan awal Data TBS biasanya dirantai dari Total TBS Restan dokumen
	sebelumnya. Rantai itu bisa salah karena hal di luar sistem — hitung fisik
	yang beda, periode lama yang angkanya rusak tapi sudah ditutup — dan
	membetulkannya dengan mengetik angka di satu Data TBS tidak bertahan: tiap
	kali rantainya dihitung ulang, angkanya tertimpa lagi oleh dokumen
	sebelumnya. Dokumen ini yang jadi patokannya, dibaca get_restan_awal dan
	hitung_ulang_rantai di Data TBS.
	"""

	def validate(self):
		self.validate_duplikat()

		if flt(self.restan_awal) < 0:
			frappe.throw(_("Restan Awal tidak boleh minus."))

	def validate_duplikat(self):
		kembar = frappe.db.get_value(self.doctype, {
			"name": ("!=", self.name),
			"unit": self.unit,
			"tanggal": self.tanggal,
			"docstatus": ("<", 2),
		})

		if kembar:
			frappe.throw(_("{0} sudah menetapkan restan awal unit {1} tanggal {2}.").format(
				frappe.bold(kembar), frappe.bold(self.unit),
				frappe.bold(frappe.format(self.tanggal, {"fieldtype": "Date"}))))

	def on_submit(self):
		self.samakan_saldo_gudang()
		self.antrikan_hitung_ulang()

	def on_cancel(self):
		# Saldo gudang dikembalikan bersama patokannya. Tanpa ini Data TBS yang
		# kembali merantai dari dokumen sebelumnya tidak cocok lagi dengan isi
		# gudangnya.
		if self.stock_reconciliation and frappe.db.get_value(
			"Stock Reconciliation", self.stock_reconciliation, "docstatus"
		) == 1:
			frappe.get_doc("Stock Reconciliation", self.stock_reconciliation).cancel()

		self.antrikan_hitung_ulang()

	def samakan_saldo_gudang(self):
		"""Bawa saldo gudang TBS ke restan awal ini, lewat Stock Reconciliation.

		Stock Entry Data TBS cuma memposting pergerakan hari itu, yaitu Total TBS
		Restan dikurangi restan awal dokumennya sendiri. Rangkaian itu bersambung
		dengan saldo gudang hanya selama restan awal dirantai dari dokumen
		sebelumnya, dan patokan ini memutusnya. Rekonsiliasi — bukan Material
		Receipt sebesar selisihnya — karena yang ditetapkan saldo, jadi hasilnya
		mendarat di angka ini berapa pun isi buku stok sebelumnya.

		Penilaiannya tidak ikut digeser: valuation_rate diisi rate yang berlaku
		persis sebelum saat ini, jadi yang berubah cuma kuantitas.
		"""
		item = frappe.db.get_value("Item", {"tipe_barang": "TBS"})
		if not item:
			frappe.throw(_("Item dengan tipe_barang TBS tidak ditemukan."))

		gudang = get_warehouse_tbs(self.unit)
		if not gudang:
			frappe.throw(_("Gudang TBS (warehouse_category TBS) unit {0} tidak ditemukan.").format(
				frappe.bold(self.unit)))

		saldo, rate = get_stock_balance(
			item, gudang, self.tanggal, WAKTU_REKONSILIASI, with_valuation_rate=True
		)

		if abs(flt(self.restan_awal) - flt(saldo)) < 0.01:
			return

		company = frappe.db.get_value("Warehouse", gudang, "company")

		sr = frappe.new_doc("Stock Reconciliation")
		sr.purpose = "Stock Reconciliation"
		sr.company = company
		sr.unit = self.unit
		sr.set_posting_time = 1
		sr.posting_date = self.tanggal
		sr.posting_time = WAKTU_REKONSILIASI
		sr.expense_account = frappe.db.get_value("Company", company, "stock_adjustment_account")
		sr.cost_center = frappe.db.get_value("Company", company, "cost_center")
		sr.append("items", {
			"item_code": item,
			"warehouse": gudang,
			"qty": flt(self.restan_awal),
			"valuation_rate": flt(rate),
		})

		# Pesan "tidak ada yang berubah" dari ERPNext dibuang: saldonya memang
		# sudah pas, bukan gagal.
		batas_pesan = len(frappe.local.message_log)
		try:
			sr.insert(ignore_permissions=True)
			sr.submit()
		except EmptyStockReconciliationItemsError:
			del frappe.local.message_log[batas_pesan:]
			return

		self.db_set("stock_reconciliation", sr.name)

	def antrikan_hitung_ulang(self):
		"""Rantai Data TBS unit ini sejak tanggal patokan dihitung ulang di latar belakang.

		Sama dengan pemicu Timbangan: fase Stock Entry-nya membatalkan dan membuat
		ulang dokumen stok untuk tiap hari sesudahnya, terlalu berat untuk
		menumpang di request submit. `flags.lewati_hitung_ulang` dipakai patch
		yang menjalankan hitung ulangnya sendiri sesudah ini.
		"""
		if self.flags.lewati_hitung_ulang:
			return

		frappe.enqueue(
			"sth.mill.doctype.data_tbs.data_tbs.hitung_ulang_rantai",
			queue="long",
			timeout=3600,
			enqueue_after_commit=True,
			unit=self.unit,
			sejak=self.tanggal,
		)

		frappe.msgprint(
			_("Data TBS unit {0} sejak {1} dihitung ulang di latar belakang, termasuk Stock Entry-nya.").format(
				self.unit, frappe.format(self.tanggal, {"fieldtype": "Date"})),
			alert=True,
			indicator="blue",
		)
