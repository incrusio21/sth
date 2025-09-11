# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe

from frappe.utils import get_link_to_form
from sth.controllers.plantation_controller import PlantationController

force_item_fields = (
	"voucher_type",
	"voucher_no"
)

class RencanaKerjaHarian(PlantationController):
	def validate(self):
		self.get_rencana_kerja_bulanan()
		self.validate_duplicate_rkh()
		self.check_material()

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

	def check_material(self):
		if self.tipe_kegiatan != "Perawatan":
			self.material = []

		material_list = [m.item for m in self.material]
		if not material_list:
			return
		
		rkb_m = frappe.qb.DocType("Detail Material RK")
		material_used = frappe._dict(
			(
				frappe.qb.from_(rkb_m)
				.select(
					rkb_m.item, rkb_m.name
				)
				.where(
					(rkb_m.item.isin(material_list)) &
					(rkb_m.parent == self.voucher_no)
				)
				.groupby(rkb_m.item)
			).run()
		)

		for d in self.material:
			rkb_material = material_used.get(d.item) or ""
			if not rkb_material:
				frappe.throw("Item {} is not listed in the {}.".format(d.item, get_link_to_form(self.voucher_type, self.voucher_no)))

			d.prevdoc_detail = rkb_material

	def on_submit(self):
		self.update_rkb_used()

	def on_cancel(self):
		self.update_rkb_used()

	def update_rkb_used(self):
		frappe.get_doc(self.voucher_type, self.voucher_no).update_used_total()

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


