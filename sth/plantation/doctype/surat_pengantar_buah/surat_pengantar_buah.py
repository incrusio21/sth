# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json
import frappe
from frappe.utils import flt
from frappe.model.document import Document

force_item_fields = (
	"bkm_panen",
)

class SuratPengantarBuah(Document):
	
	def validate(self):
		self.remove_input_pabrik()
		self.get_bkm_panen()
		self.calculate_janjang_brondolan()

	def remove_input_pabrik(self):
		self.in_time = self.out_time = ""
		self.in_weight = self.out_weight = self.pabrik_cut = self.netto_weight = self.total_weight = 0

	def get_bkm_panen(self):
		for d in self.details:
			ret = get_bkm_panen(d.blok, d.panen_date)
			for fieldname, value in ret.items():
				if self.meta.get_field(fieldname) and value is not None:
					if (
						self.get(fieldname) is None
						or fieldname in force_item_fields
					):
						self.set(fieldname, value)

	def calculate_janjang_brondolan(self):
		total_janjang = total_brondolan = 0.0
		for d in self.details:
			total_janjang += d.qty
			total_brondolan += d.brondolan_qty
			d.netto_weight = d.total_weight = 0.0

		self.total_janjang = total_janjang
		self.total_brondolan = total_brondolan

	def on_submit(self):
		self.update_transfered_bkm_panen()

	def on_cancel(self):
		self.update_transfered_bkm_panen()

	def update_transfered_bkm_panen(self):
		for d in self.details:
			doc = frappe.get_doc("Buku Kerja Mandor Panen", d.bkm_panen)
			doc.calculate_transfered_weight()

	@frappe.whitelist()
	def set_pabrik_weight(self, args):
		if isinstance(args, str):
			args = json.loads(args)
		
		self.pabrik_cut = 0.0
		
		self.update(args)

		# hitung janjang dan total brondolan terlebih dahulu
		self.calculate_janjang_brondolan()

		if self.in_weight and self.out_weight:
			self.netto_weight = flt(self.in_weight - self.out_weight - self.total_brondolan - self.pabrik_cut, self.precision("netto_weight"))
			self.total_weight = self.netto_weight + self.total_brondolan

		for d in self.details:
			d.netto_weight = flt((self.netto_weight * d.qty / self.total_janjang), d.precision("netto_weight"))
			d.total_weight = d.netto_weight + d.brondolan_qty

		self.db_update_all()
		self.update_transfered_bkm_panen()

@frappe.whitelist()
def get_bkm_panen(blok, posting_date):
	bkm_panen = frappe.get_value("Buku Kerja Mandor Panen", {
		"blok": blok, "posting_date": posting_date, "docstatus": 1
	}, ["name", 
	 	"hasil_kerja_qty", "transfered_hasil_kerja",
		"hasil_kerja_qty_brondolan", "transfered_brondolan", "is_rekap"
	], as_dict=1)

	if not bkm_panen:
		frappe.throw(""" Buku Kerja Mandor Panen not Found for Filters <br> 
			Blok : {} <br> 
			Date : {} """.format(blok, posting_date))
	
	if bkm_panen.is_rekap:
		frappe.throw("Buku Kerja Mandor Panen already have Rekap Timbangan Panen")

	ress = { 
		"bkm_panen": bkm_panen.name,
		"qty": flt(bkm_panen.hasil_kerja_qty - bkm_panen.transfered_hasil_kerja),
		"brondolan_qty": flt(bkm_panen.hasil_kerja_qty_brondolan - bkm_panen.transfered_brondolan),
	}

	return ress