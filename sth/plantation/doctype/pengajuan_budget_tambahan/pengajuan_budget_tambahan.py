# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from sth.controllers.plantation_controller import PlantationController

force_item_fields = (
	"voucher_type",
	"voucher_no"
)


class PengajuanBudgetTambahan(PlantationController):
	def validate(self):
		# memaksa material menjadi array kosong
		if self.tipe_kegiatan != "Perawatan":
			self.material = []

		# self.get_rencana_kerja_bulanan()
		self.validate_duplicate_pbt()
		# self.validate_previous_document()

		super().validate()

	def get_rencana_kerja_bulanan(self):
		ret = get_rencana_kerja_bulanan(self.kode_kegiatan, self.tipe_kegiatan, self.divisi, self.blok, self.posting_date)
		for fieldname, value in ret.items():
			if self.meta.get_field(fieldname) and value is not None:
				if (
					self.get(fieldname) is None
					or fieldname in force_item_fields
				):
					self.set(fieldname, value)

	def validate_duplicate_pbt(self):
		if doc := frappe.db.get_value("Pengajuan Budget Tambahan", {
			"kode_kegiatan": self.kode_kegiatan, "divisi": self.divisi, "blok": self.blok, "posting_date": self.posting_date,
			"docstatus": 1, "name": ["!=", self.name]
		}, pluck="name"):
			frappe.throw("Pengajuan Budget Tambahan already Used in {}".format(doc))

	# def validate_previous_document(self):
	# 	from sth.controllers.prev_doc_validate import validate_previous_document

	# 	validate_previous_document(self)

	def on_submit(self):
		voucher_type = frappe.get_value("Tipe Kegiatan", self.tipe_kegiatan, "rkb_voucher_type")
		rkb = frappe.db.get_value(voucher_type, {
			"kode_kegiatan": self.kode_kegiatan, "divisi": self.divisi, "blok": self.blok, "from_date": ["<=", self.posting_date], "to_date": [">=", self.posting_date],
			"docstatus": 1
		}, "name")

		if self.tipe_kegiatan == "Perawatan":
			self.update_rkb_perawatan(rkb)
		elif self.tipe_kegiatan == "Traksi":
			self.update_rkb_traksi(rkb)

		# self.update_pbt_used()

	def update_rkb_perawatan(self, rkb):
		doc = frappe.get_doc("Rencana Kerja Bulanan Perawatan", rkb)

		if doc:
			doc.tambahan_kode_kegiatan = self.kode_kegiatan
			doc.tambahan_tipe_kegiatan = self.tipe_kegiatan
			doc.tambahan_tipe_kegiatan = self.tipe_kegiatan
			doc.tambahan_rate_basis = self.rate_basis
			doc.tambahan_volume_basis = self.volume_basis
			doc.tambahan_target_volume = self.target_volume
			doc.tambahan_qty_tenaga_kerja = self.qty_tenaga_kerja

			tambahan_tenaga_kerja_amount = self.qty_tenaga_kerja * self.rate_basis
			tambahan_material_amount = sum([row.amount or 0 for row in self.material])
			budget_tambahan_amount = tambahan_tenaga_kerja_amount + tambahan_material_amount
			
			doc.tambahan_tenaga_kerja_amount = tambahan_tenaga_kerja_amount
			doc.tambahan_material_amount = tambahan_material_amount
			doc.budget_tambahan_amount = budget_tambahan_amount

			for row in self.material:
				doc.append("tambahan_material", {
					"item": row.item,
					"uom": row.uom,
					"dosis": row.dosis,
					"qty": row.qty,
					"rate": row.rate,
					"amount": row.amount
				})

			doc.flags.ignore_validate = True
			doc.flags.ignore_permissions = True
			doc.save()

	def update_rkb_traksi(self, rkb):
		doc = frappe.get_doc("Rencana Kerja Bulanan Pengangkutan Panen", rkb)

		if doc:
			for row in self.kendaraan:
				doc.append("kendaraan_tambahan", {
					"item": row.item,
					"uom": row.uom,
					"kap_kg": row.kap_kg,
					"qty": row.qty,
					"rate": row.rate,
					"amount": row.amount
				})

			for row in self.biaya_angkut:
				doc.append("angkut_tambahan", {
					"item": row.item,
					"jumlah_hk": row.jumlah_hk,
					"basis": row.basis,
					"qty": row.qty,
					"rate": row.rate,
					"amount": row.amount
				})

			tambahan_kendaraan_amount = sum([row.amount or 0 for row in self.kendaraan])
			tambahan_angkut_amount = sum([row.amount or 0 for row in self.biaya_angkut])
			budget_tambahan_amount = tambahan_kendaraan_amount + tambahan_angkut_amount

			doc.tambahan_kendaraan_amount = tambahan_kendaraan_amount
			doc.tambahan_angkut_amount = tambahan_angkut_amount
			doc.budget_tambahan_amount = budget_tambahan_amount

			doc.flags.ignore_validate = True
			doc.flags.ignore_permissions = True
			doc.save()

	# def on_cancel(self):
	# 	self.update_pbt_used()

	# def update_pbt_used(self):
	# 	frappe.get_doc(self.voucher_type, self.voucher_no).calculate_used_and_realized()

@frappe.whitelist()
def get_rencana_kerja_bulanan(kode_kegiatan, tipe_kegiatan, divisi, blok, posting_date):
	voucher_type = frappe.get_value("Tipe Kegiatan", tipe_kegiatan, "rkb_voucher_type")
	rkb = frappe.db.get_value(voucher_type, {
		"kode_kegiatan": kode_kegiatan, "divisi": divisi, "blok": blok, "from_date": ["<=", posting_date], "to_date": [">=", posting_date],
		"docstatus": 1
	}, "name")

	if not rkb:
		frappe.throw(""" {} not Found for Filters <br> 
			Kegiatan : {} <br> 
			Divisi : {} <br> 
			Blok : {} <br>
			Date : {} """.format(voucher_type, kode_kegiatan, divisi, blok, posting_date))

	# no rencana kerja bualanan
	ress = { "voucher_type": voucher_type, "voucher_no": rkb}
	if voucher_type == "Rencana Kerja Bulanan Perawatan":
		ress["material"] = frappe.db.get_all("Detail Material RK", 
			filters={"parent": rkb}, fields=["item", "rate", "uom", "name as prevdoc_detail"]
		)

	return ress
