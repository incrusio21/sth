# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, nowdate

STATE_APPROVED = "Approved"

# status asset yang tidak bisa lagi diajukan scrap
STATUS_TIDAK_BISA_SCRAP = ("Draft", "Cancelled", "Sold", "Scrapped", "Capitalized", "Decapitalized")


def nilai_buku_asset(asset):
	"""Nilai buku seluruh Asset, apa pun cara penyusutannya."""
	if asset.calculate_depreciation and asset.get("finance_books"):
		return flt(asset.finance_books[0].value_after_depreciation)

	return flt(asset.value_after_depreciation) or (
		flt(asset.gross_purchase_amount) - flt(asset.opening_accumulated_depreciation)
	)


class AssetScrapRequest(Document):

	def validate(self):
		self.validate_asset()
		self.validate_duplikat()
		self.validate_persentase()
		self.set_nilai_buku()

	def validate_asset(self):
		asset = frappe.db.get_value(
			"Asset", self.asset, ["docstatus", "status", "company"], as_dict=True
		)

		if not asset:
			frappe.throw(_("Asset {0} tidak ditemukan").format(self.asset))

		if asset.docstatus != 1:
			frappe.throw(_("Asset {0} belum disubmit").format(self.asset))

		if asset.status in STATUS_TIDAK_BISA_SCRAP:
			frappe.throw(
				_("Asset {0} tidak bisa discrap karena statusnya {1}").format(self.asset, asset.status)
			)

	def validate_duplikat(self):
		# yang dilarang cuma pengajuan yang masih berjalan. pengajuan yang ditolak
		# berdocstatus 1, jadi asetnya tetap bisa diajukan ulang
		pengajuan_lain = frappe.db.exists(
			"Asset Scrap Request",
			{
				"asset": self.asset,
				"docstatus": 0,
				"name": ["!=", self.name]
			}
		)

		if pengajuan_lain:
			frappe.throw(
				_("Asset {0} sudah punya pengajuan scrap yang berjalan").format(self.asset)
			)

	def validate_persentase(self):
		# asset_quantity ikut fetch_from, tapi asset lama bisa saja masih kosong
		total = cint(self.asset_quantity) or cint(
			frappe.db.get_value("Asset", self.asset, "asset_quantity")
		) or 1
		self.asset_quantity = total

		if not flt(self.persentase_scrap):
			if cint(self.qty_scrap):
				# pengajuan yang dibuat sebelum ada input persentase: rasionya
				# diambil dari qty supaya nilainya tidak berubah di tengah approval
				self.persentase_scrap = flt(
					cint(self.qty_scrap) * 100 / total, self.precision("persentase_scrap")
				)
			else:
				# tanpa pengisian, perlakuannya seperti sebelum ada scrap sebagian
				self.persentase_scrap = 100

		if flt(self.persentase_scrap) <= 0:
			frappe.throw(_("Persentase Discrap harus lebih besar dari 0"))

		if flt(self.persentase_scrap) > 100:
			frappe.throw(_("Persentase Discrap tidak boleh lebih dari 100"))

		self.qty_scrap = self.hitung_qty_scrap()

	def hitung_qty_scrap(self):
		"""Qty yang mewakili persentase, cuma untuk ditampilkan dan dipasang ke
		asset pecahan. Yang menentukan pembagian nilai tetap persentasenya."""
		total = cint(self.asset_quantity) or 1
		persentase = flt(self.persentase_scrap)

		if persentase >= 100:
			return total

		qty = cint(round(total * persentase / 100.0)) or 1

		if total > 1:
			# asset sisa harus tetap punya qty
			qty = min(qty, total - 1)

		return qty

	def set_nilai_buku(self):
		asset = frappe.get_doc("Asset", self.asset)

		if not flt(self.gross_purchase_amount):
			self.gross_purchase_amount = flt(asset.gross_purchase_amount)

		nilai_buku = nilai_buku_asset(asset)

		persentase = flt(self.persentase_scrap) or 100
		if persentase < 100:
			# yang ditampilkan nilai buku sebesar bagian yang discrap saja
			nilai_buku = nilai_buku * persentase / 100.0

		self.nilai_buku = flt(nilai_buku, self.precision("nilai_buku"))

	def on_update(self):
		# dipanggil di tiap transisi workflow, termasuk saat submit
		self.update_status_scrap()

	def update_status_scrap(self, kosongkan=False):
		"""Cerminkan state pengajuan ke Asset supaya kelihatan di list view."""
		status = "" if kosongkan else (self.get("workflow_state") or "")

		frappe.db.set_value("Asset", self.asset, "status_scrap", status, update_modified=False)

	def on_submit(self):
		# workflow punya dua state ber-docstatus 1: Approved dan Rejected.
		# yang boleh menjalankan scrap cuma Approved.
		if self.get("workflow_state") and self.workflow_state != STATE_APPROVED:
			return

		self.scrap_asset()

	def scrap_asset(self):
		self.validate_asset()

		if flt(self.persentase_scrap) >= 100:
			self.scrap_seluruh_asset()
			return

		self.hapus_buku_bagian_yang_discrap()

	def scrap_seluruh_asset(self):
		# import langsung supaya tidak kena penjaga di sth.overrides.asset.scrap_asset
		from erpnext.assets.doctype.asset.depreciation import scrap_asset

		frappe.flags.ignore_asset_scrap_request = True
		try:
			scrap_asset(self.asset)
		finally:
			frappe.flags.ignore_asset_scrap_request = False

		journal_entry = frappe.db.get_value("Asset", self.asset, "journal_entry_for_scrap")
		if journal_entry:
			self.db_set("journal_entry_for_scrap", journal_entry)

	def hapus_buku_bagian_yang_discrap(self):
		"""Hapus buku porsi yang discrap langsung dari asset asalnya.

		Asetnya sengaja tidak dipecah jadi dokumen baru. Nilai perolehan, akumulasi
		penyusutan, dan nilai bukunya dikurangi sebesar porsi yang discrap, lalu qty
		yang discrap dicatat di Asset. Sebanyak qty itulah yang boleh dijual lewat
		Sales Invoice Disposal."""
		asset = frappe.get_doc("Asset", self.asset)

		je = self.buat_jurnal_hapus_buku(asset)
		self.db_set("journal_entry_for_scrap", je)

		self.geser_nilai_asset(asset, -1)

		if asset.calculate_depreciation:
			frappe.msgprint(
				_("Nilai Asset {0} sudah dikurangi, tapi jadwal penyusutannya belum ikut "
				  "disesuaikan. Sesuaikan lewat Asset Value Adjustment kalau penyusutan "
				  "berikutnya harus ikut turun.").format(self.asset),
				title=_("Jadwal Penyusutan Belum Disesuaikan"),
				indicator="orange"
			)

	def porsi_yang_discrap(self):
		"""Harga perolehan, akumulasi penyusutan, dan nilai buku sebesar porsi yang
		discrap.

		Diambil dari angka yang tersimpan di pengajuan ini, bukan dihitung ulang dari
		Asset, supaya pembatalan mengembalikan angka yang persis sama dengan yang
		dipakai waktu jurnalnya dibuat."""
		persen = flt(self.persentase_scrap) / 100.0

		gross = flt(flt(self.gross_purchase_amount) * persen, self.precision("gross_purchase_amount"))
		nilai_buku = flt(self.nilai_buku)
		akumulasi = max(flt(gross - nilai_buku, self.precision("nilai_buku")), 0)

		return gross, akumulasi, nilai_buku

	def akun_scrap(self, asset):
		"""Akun aset tetap, akumulasi penyusutan, akun pelepasan, dan cost center."""
		from erpnext.assets.doctype.asset.depreciation import get_disposal_account_and_cost_center

		baris = frappe.db.get_value(
			"Asset Category Account",
			{"parent": asset.asset_category, "company_name": self.company},
			["fixed_asset_account", "accumulated_depreciation_account"],
			as_dict=True
		)

		if not baris or not baris.fixed_asset_account:
			frappe.throw(
				_("Akun Aset Tetap untuk Company {0} belum diisi di Asset Category {1}").format(
					self.company, asset.asset_category
				)
			)

		akun_pelepasan, cost_center = get_disposal_account_and_cost_center(self.company)

		return frappe._dict({
			"aset_tetap": baris.fixed_asset_account,
			"akumulasi": baris.accumulated_depreciation_account,
			"pelepasan": akun_pelepasan,
			"cost_center": asset.cost_center or cost_center,
		})

	def buat_jurnal_hapus_buku(self, asset):
		akun = self.akun_scrap(asset)
		gross, akumulasi, nilai_buku = self.porsi_yang_discrap()

		if gross <= 0:
			frappe.throw(_("Harga perolehan porsi yang discrap harus lebih besar dari 0"))

		if akumulasi > 0 and not akun.akumulasi:
			frappe.throw(
				_("Akun Akumulasi Penyusutan untuk Company {0} belum diisi di Asset Category {1}").format(
					self.company, asset.asset_category
				)
			)

		keterangan = _("Scrap {0}% Asset {1} - {2}").format(
			flt(self.persentase_scrap), self.asset, self.name
		)

		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Journal Entry"
		je.company      = self.company
		je.posting_date = self.posting_date or nowdate()
		je.user_remark  = keterangan

		def baris_jurnal(account, debit=0, credit=0):
			je.append("accounts", {
				"account"                   : account,
				"debit_in_account_currency" : debit,
				"credit_in_account_currency": credit,
				"cost_center"               : akun.cost_center,
				"reference_type"            : "Asset",
				"reference_name"            : asset.name,
				"user_remark"               : keterangan,
			})

		if akumulasi > 0:
			baris_jurnal(akun.akumulasi, debit=akumulasi)

		if nilai_buku > 0:
			baris_jurnal(akun.pelepasan, debit=nilai_buku)

		baris_jurnal(akun.aset_tetap, credit=gross)

		je.insert(ignore_permissions=True)
		je.submit()

		frappe.msgprint(f"Journal Entry <b>{je.name}</b> berhasil dibuat.", alert=True)

		return je.name

	def geser_nilai_asset(self, asset, arah):
		"""Kurangi (arah -1) atau kembalikan (arah 1) nilai asset sebesar porsi yang
		discrap, sekalian qty yang boleh dijual."""
		gross, akumulasi, nilai_buku = self.porsi_yang_discrap()
		qty_scrap = self.hitung_qty_scrap()
		qty_total = cint(asset.asset_quantity) or 1

		gross_baru = max(flt(asset.gross_purchase_amount) + arah * gross, 0)

		nilai = {
			"gross_purchase_amount": gross_baru,
			"total_asset_cost": gross_baru,
			"opening_accumulated_depreciation": max(
				flt(asset.opening_accumulated_depreciation) + arah * akumulasi, 0
			),
			"value_after_depreciation": max(
				flt(asset.value_after_depreciation) + arah * nilai_buku, 0
			),
			"qty_scrapped": max(cint(asset.get("qty_scrapped")) - arah * qty_scrap, 0),
		}

		# qty asset cuma digeser kalau waktu pengajuan ini dulu masih ada sisanya.
		# asset ber-qty 1 yang discrap sebagian nilainya tetap dihitung 1 unit
		if cint(self.asset_quantity) > qty_scrap:
			nilai["asset_quantity"] = max(qty_total + arah * qty_scrap, 1)

		frappe.db.set_value("Asset", asset.name, nilai, update_modified=False)

		for row in asset.get("finance_books"):
			frappe.db.set_value(
				"Asset Finance Book",
				row.name,
				"value_after_depreciation",
				max(flt(row.value_after_depreciation) + arah * nilai_buku, 0),
				update_modified=False
			)

	def on_cancel(self):
		if self.journal_entry_for_scrap:
			if flt(self.persentase_scrap) >= 100:
				frappe.throw(
					_("Asset {0} sudah discrap seluruhnya. Batalkan lewat tombol Restore Asset "
					  "di Asset tersebut.").format(self.asset)
				)

			self.batalkan_hapus_buku()

		self.update_status_scrap(kosongkan=True)

	def batalkan_hapus_buku(self):
		"""Kembalikan nilai dan qty yang dipotong waktu scrap sebagian disetujui."""
		from sth.overrides.asset import sisa_qty_scrap

		if sisa_qty_scrap(self.asset) < self.hitung_qty_scrap():
			frappe.throw(
				_("Bagian yang discrap dari Asset {0} sudah terjual, pengajuan ini tidak bisa "
				  "dibatalkan.").format(self.asset)
			)

		je = frappe.get_doc("Journal Entry", self.journal_entry_for_scrap)
		if je.docstatus == 1:
			je.cancel()

		self.geser_nilai_asset(frappe.get_doc("Asset", self.asset), 1)
		self.db_set("journal_entry_for_scrap", None)

	def on_trash(self):
		self.update_status_scrap(kosongkan=True)


def get_pengajuan_berjalan(asset):
	return frappe.db.get_value("Asset Scrap Request", {"asset": asset, "docstatus": 0}, "name")


@frappe.whitelist()
def get_status_scrap(asset):
	"""Dipakai form Asset. Semua approval dikerjakan dari sana, dokumen
	Asset Scrap Request cuma pencatat di belakang layar."""
	from frappe.model.workflow import get_transitions

	asset_doc = frappe.db.get_value(
		"Asset", asset, ["docstatus", "status", "asset_quantity"], as_dict=True
	)
	if not asset_doc:
		return None

	hasil = {
		"name": None,
		"workflow_state": None,
		"actions": [],
		"asset_quantity": cint(asset_doc.asset_quantity) or 1,
		"persentase_scrap": None,
		"qty_scrap": None,
		"bisa_ajukan": (
			asset_doc.docstatus == 1 and asset_doc.status not in STATUS_TIDAK_BISA_SCRAP
		)
	}

	nama = get_pengajuan_berjalan(asset)
	if not nama:
		return hasil

	doc = frappe.get_doc("Asset Scrap Request", nama)

	hasil["name"] = doc.name
	hasil["workflow_state"] = doc.get("workflow_state")
	hasil["actions"] = [transisi.action for transisi in get_transitions(doc, raise_exception=False)]
	hasil["persentase_scrap"] = flt(doc.persentase_scrap)
	hasil["qty_scrap"] = cint(doc.qty_scrap)
	hasil["bisa_ajukan"] = False

	return hasil


@frappe.whitelist()
def ajukan_scrap(asset, alasan, lampiran=None, persentase_scrap=None):
	"""Buat pengajuan lalu langsung dorong ke lapis approval pertama."""
	from frappe.model.workflow import apply_workflow, get_transitions

	if get_pengajuan_berjalan(asset):
		frappe.throw(_("Asset {0} sudah punya pengajuan scrap yang berjalan").format(asset))

	doc = frappe.new_doc("Asset Scrap Request")
	doc.asset = asset
	doc.alasan = alasan
	doc.lampiran = lampiran
	doc.persentase_scrap = flt(persentase_scrap)
	doc.insert()

	transisi = get_transitions(doc, raise_exception=False)
	if not transisi:
		# jalur approval unit ini belum ada, atau role user tidak boleh mengajukan
		frappe.throw(
			_("Belum ada jalur approval scrap yang cocok untuk unit {0}. Atur di Asset Scrap Settings.").format(
				doc.unit or "-"
			)
		)

	apply_workflow(doc, transisi[0].action)

	return doc.get("workflow_state")


@frappe.whitelist()
def proses_scrap(asset, action):
	"""Jalankan aksi workflow (Approve/Reject) dari form Asset.
	apply_workflow yang memeriksa apakah role user boleh menjalankannya."""
	from frappe.model.workflow import apply_workflow

	nama = get_pengajuan_berjalan(asset)
	if not nama:
		frappe.throw(_("Tidak ada pengajuan scrap yang berjalan untuk Asset {0}").format(asset))

	doc = frappe.get_doc("Asset Scrap Request", nama)
	apply_workflow(doc, action)

	return doc.get("workflow_state")
