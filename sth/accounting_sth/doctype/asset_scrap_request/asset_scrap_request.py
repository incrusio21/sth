# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

STATE_APPROVED = "Approved"

# status asset yang tidak bisa lagi diajukan scrap
STATUS_TIDAK_BISA_SCRAP = ("Draft", "Cancelled", "Sold", "Scrapped", "Capitalized", "Decapitalized")


class AssetScrapRequest(Document):

	def validate(self):
		self.validate_asset()
		self.validate_duplikat()
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

	def set_nilai_buku(self):
		asset = frappe.get_doc("Asset", self.asset)

		if asset.calculate_depreciation and asset.get("finance_books"):
			nilai_buku = flt(asset.finance_books[0].value_after_depreciation)
		else:
			nilai_buku = flt(asset.value_after_depreciation) or (
				flt(asset.gross_purchase_amount) - flt(asset.opening_accumulated_depreciation)
			)

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
		# import langsung supaya tidak kena penjaga di sth.overrides.asset.scrap_asset
		from erpnext.assets.doctype.asset.depreciation import scrap_asset

		self.validate_asset()

		frappe.flags.ignore_asset_scrap_request = True
		try:
			scrap_asset(self.asset)
		finally:
			frappe.flags.ignore_asset_scrap_request = False

		journal_entry = frappe.db.get_value("Asset", self.asset, "journal_entry_for_scrap")
		if journal_entry:
			self.db_set("journal_entry_for_scrap", journal_entry)

	def on_cancel(self):
		if self.journal_entry_for_scrap:
			frappe.throw(
				_("Asset {0} sudah discrap. Batalkan lewat tombol Restore Asset di Asset tersebut.").format(
					self.asset
				)
			)

		self.update_status_scrap(kosongkan=True)

	def on_trash(self):
		self.update_status_scrap(kosongkan=True)


def get_pengajuan_berjalan(asset):
	return frappe.db.get_value("Asset Scrap Request", {"asset": asset, "docstatus": 0}, "name")


@frappe.whitelist()
def get_status_scrap(asset):
	"""Dipakai form Asset. Semua approval dikerjakan dari sana, dokumen
	Asset Scrap Request cuma pencatat di belakang layar."""
	from frappe.model.workflow import get_transitions

	asset_doc = frappe.db.get_value("Asset", asset, ["docstatus", "status"], as_dict=True)
	if not asset_doc:
		return None

	hasil = {
		"name": None,
		"workflow_state": None,
		"actions": [],
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
	hasil["bisa_ajukan"] = False

	return hasil


@frappe.whitelist()
def ajukan_scrap(asset, alasan, lampiran=None):
	"""Buat pengajuan lalu langsung dorong ke lapis approval pertama."""
	from frappe.model.workflow import apply_workflow, get_transitions

	if get_pengajuan_berjalan(asset):
		frappe.throw(_("Asset {0} sudah punya pengajuan scrap yang berjalan").format(asset))

	doc = frappe.new_doc("Asset Scrap Request")
	doc.asset = asset
	doc.alasan = alasan
	doc.lampiran = lampiran
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
