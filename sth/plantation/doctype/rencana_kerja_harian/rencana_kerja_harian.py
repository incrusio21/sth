# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import unscrub
from frappe.utils import cint, flt

from sth.controllers.plantation_controller import PlantationController

force_item_fields = (
	"voucher_type",
	"voucher_no"
)

class RencanaKerjaHarian(PlantationController):
	def update_rate_or_qty_value(self, item, precision):
		if item.parentfield == "material" and self.target_volume:
			item.qty = flt(item.dosis / self.target_volume, precision)

	def validate(self):
		# memaksa material menjadi array kosong
		if self.tipe_kegiatan != "Perawatan":
			self.material = []

		self.get_rencana_kerja_bulanan()
		self.validate_duplicate_rkh()
		self.validate_previous_document()
		self.calculate_kegiatan_amount()

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
		
	def validate_duplicate_rkh(self):
		if doc := frappe.db.get_value("Rencana Kerja Harian", {
			"kode_kegiatan": self.kode_kegiatan, "divisi": self.divisi, "blok": self.blok, "posting_date": self.posting_date,
			"docstatus": 1, "name": ["!=", self.name]
		}, pluck="name"):
			frappe.throw("Rencan Kerja Harian already Used in {}".format(doc))

	def validate_previous_document(self):
		from sth.controllers.prev_doc_validate import validate_previous_document

		validate_previous_document(self)

	def calculate_kegiatan_amount(self):
		if not self.qty_tenaga_kerja:
			self.qty_tenaga_kerja = flt(self.target_volume / self.volume_basis) if self.volume_basis else 0

		qty = self.target_volume if self.tipe_kegiatan == "Panen" else self.qty_tenaga_kerja 
		self.kegiatan_amount = flt(self.rate_basis * qty)

	def on_submit(self):
		self.update_rkb_used()

	def on_cancel(self):
		self.update_rkb_used()

	def update_rkb_used(self):
		frappe.get_doc(self.voucher_type, self.voucher_no).calculate_used_and_realized()

@frappe.whitelist()
def get_rencana_kerja_bulanan(kode_kegiatan, tipe_kegiatan, divisi, blok, posting_date, is_bibitan=False):
	voucher_type = frappe.get_value("Tipe Kegiatan", tipe_kegiatan, "rkb_voucher_type")
	fieldname = "batch" if cint(is_bibitan) else "blok"

	rkb = frappe.db.get_value(voucher_type, {
		"kode_kegiatan": kode_kegiatan, "divisi": divisi, fieldname: blok, "from_date": ["<=", posting_date], "to_date": [">=", posting_date],
		"docstatus": 1
	}, "name")

	if not rkb:
		frappe.throw(""" {} not Found for Filters <br> 
			Kegiatan : {} <br> 
			Divisi : {} <br> 
			{} : {} <br>
			Date : {} """.format(voucher_type, kode_kegiatan, divisi, unscrub(fieldname), blok, posting_date))

	# no rencana kerja bualanan
	ress = { "voucher_type": voucher_type, "voucher_no": rkb}
	if voucher_type == "Rencana Kerja Bulanan Perawatan":
		ress["material"] = frappe.db.get_all("Detail Material RK", 
			filters={"parent": rkb}, fields=["item", "rate", "uom", "name as prevdoc_detail"]
		)
	if voucher_type == "Rencana Kerja Bulanan Pengangkutan Panen":
		ress["kendaraan"] = frappe.db.get_all("RKB Pengangkutan Kendaraan",
			filters={"parent": rkb}, fields=["item", "uom", "kap_kg", "qty", "rate", "amount"]
		)

	return ress


