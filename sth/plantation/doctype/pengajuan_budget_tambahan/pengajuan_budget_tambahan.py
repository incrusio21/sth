# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe

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
		self.update_pbt_used()

	def on_cancel(self):
		self.update_pbt_used()

	def update_pbt_used(self):
		frappe.get_doc(self.voucher_type, self.voucher_no).calculate_used_and_realized()

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
