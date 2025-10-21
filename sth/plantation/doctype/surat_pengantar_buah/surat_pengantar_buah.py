# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json
import frappe
from frappe.model.meta import get_field_precision
from frappe.utils import flt
from frappe.model.document import Document

force_item_fields = (
	"bkm_panen",
)

class SuratPengantarBuah(Document):
	
	def validate(self):
		self.remove_input_pabrik()
		self.get_bkm_panen()
		self.calculate_janjang()

	def remove_input_pabrik(self):
		self.in_time = self.out_time = self.in_time_internal = self.out_time_internal = ""
		self.in_weight = self.in_weight_internal = self.out_weight = self.out_weight_internal = self.mill_cut = 0

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

			# cek data blok restan
			if d.blok_restan:
				ret_restan = get_bkm_panen(d.blok_restan, d.panen_date_restan)
				for fieldname, value in ret_restan.items():
					if self.meta.get_field(fieldname) and value is not None:
						if (
							self.get(f"{fieldname}_restan") is None
							or fieldname in force_item_fields
						):
							self.set(f"{fieldname}_restan", value)

	def calculate_janjang(self):
		total_janjang = 0.0
		for d in self.details:
			
			if not d.blok_restan:
				d.qty_restan = 0

			d.total_janjang = d.qty + d.qty_restan

			total_janjang += d.total_janjang

			d.total_weight = 0.0

		self.total_janjang = total_janjang

	def on_submit(self):
		self.update_transfered_bkm_panen()

	def on_cancel(self):
		self.update_transfered_bkm_panen()

	def update_transfered_bkm_panen(self):
		for d in self.details:
			doc = frappe.get_doc("Buku Kerja Mandor Panen", d.bkm_panen)
			doc.calculate_transfered_weight()

			if d.bkm_panen_restan:
				doc = frappe.get_doc("Buku Kerja Mandor Panen", d.bkm_panen_restan)
				doc.calculate_transfered_weight()

	def before_update_after_submit(self):
		if self.workflow_state != "Weighed":
			return
		
		self.weighed_cannot_update()

	def weighed_cannot_update(self):
		if not (self.out_weight and self.in_weight):
			frappe.throw("Set Weight before Save")

		doc_before = self._doc_before_save

		in_time_unchanged = doc_before.in_time == self.in_time
		out_time_unchanged = doc_before.out_time == self.out_time
		in_weight_unchanged = doc_before.in_weight == self.in_weight
		out_weight_unchanged = doc_before.out_weight == self.out_weight
		mill_cut_unchanged = doc_before.mill_cut == self.mill_cut
		
		in_time_internal_unchanged = doc_before.in_time_internal == self.in_time_internal
		out_time_internal_unchanged = doc_before.out_time_internal == self.out_time_internal
		in_weight_internal_unchanged = doc_before.in_weight_internal == self.in_weight_internal
		out_weight_internal_unchanged = doc_before.out_weight_internal == self.out_weight_internal
		
		if not (
			in_time_unchanged
			and out_time_unchanged
			and in_weight_unchanged
			and out_weight_unchanged
			and mill_cut_unchanged
			and in_time_internal_unchanged
			and out_time_internal_unchanged
			and in_weight_internal_unchanged
			and out_weight_internal_unchanged
		):
			frappe.throw("Weigh cannot be changed")
			
	@frappe.whitelist()
	def set_pabrik_weight(self, args):
		if isinstance(args, str):
			args = json.loads(args)
		
		self.update(args)
		self._calculate_weight()

		self.flags.ignore_validate_update_after_submit = True
		self.save()

	def _calculate_weight(self):
		self.calculate_total_weight()
		self.calculate_weight_in_blok()

	def calculate_total_weight(self):
		if self.out_weight and self.in_weight:
			self.total_weight = flt(self.in_weight - self.out_weight - self.mill_cut, self.precision("total_weight"))
			self.bjr = flt(self.total_weight / self.total_janjang, self.precision("bjr"))
		
		if self.total_weight < 0:
			frappe.throw("Out weight is greater than In weight")

		if self.out_weight_internal and self.in_weight_internal:
			self.total_weight_internal = flt(self.in_weight_internal - self.out_weight_internal, self.precision("total_weight_internal"))
			self.bjr_internal = flt(self.total_weight_internal / self.total_janjang, self.precision("bjr"))

		if self.total_weight_internal < 0:
			frappe.throw("Out weight is greater than In weight")

	def calculate_weight_in_blok(self):
		precision = get_field_precision(
			frappe.get_meta("SPB Timbangan Pabrik").get_field("total_weight")
		)
		for d in self.details:
			d.total_weight = flt(self.total_weight * d.total_janjang / self.total_janjang, precision)

			
@frappe.whitelist()
def get_bkm_panen(blok, posting_date):
	bkm_panen = frappe.get_value("Buku Kerja Mandor Panen", {
		"blok": blok, "posting_date": posting_date, "docstatus": 1
	}, ["name", 
	 	"hasil_kerja_jumlah_janjang", "transfered_janjang",
		"is_rekap"
	], as_dict=1)

	if not bkm_panen:
		frappe.throw(""" Buku Kerja Mandor Panen not Found for Filters <br> 
			Blok : {} <br> 
			Date : {} """.format(blok, posting_date))
	
	ress = { 
		"bkm_panen": bkm_panen.name,
		"qty": flt(bkm_panen.hasil_kerja_jumlah_janjang - bkm_panen.transfered_janjang),
	}

	return ress