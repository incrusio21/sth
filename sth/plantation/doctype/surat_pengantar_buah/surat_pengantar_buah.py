# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import unscrub
from frappe.model.meta import get_field_precision
from frappe.utils import flt
from frappe.model.document import Document

force_item_fields = (
	"recap_panen"
)

class SuratPengantarBuah(Document):
	
	def validate(self):
		self.remove_input_pks()
		self.set_missing_value()
		self.validate_recap_panen()
		self.calculate_janjang()

	def remove_input_pks(self):
		self.in_time = self.out_time = self.in_time_internal = self.out_time_internal = ""
		self.in_weight = self.in_weight_internal = self.out_weight = self.out_weight_internal = self.mill_cut = 0

	def set_missing_value(self):
		def _apply_recap(detail, suffix=""):
			blok = detail.get(f"blok{suffix}")
			panen_date = detail.get(f"panen_date{suffix}")
			
			ret = get_recap_panen(blok, panen_date)
			
			for fieldname, value in ret.items():
				target_field = f"{fieldname}{suffix}"
				
				if not (detail.meta.get_field(target_field) and value is not None):
					continue
				
				if detail.get(target_field) is None or target_field in force_item_fields:
					detail.set(target_field, value)

		for d in self.details:
			_apply_recap(d)

			# Process restan recap if exists
			if d.blok_restan and d.panen_date_restan:
				_apply_recap(d, suffix="_restan")

	def validate_recap_panen(self):
		rpb = frappe.qb.DocType("Recap Panen by Blok")

		query = (
			frappe.qb.from_(rpb)
			.select(rpb.kontanan, rpb.voucher_no)
			.where(
				(rpb.voucher_type == "Buku Kerja Mandor Panen") & 
				(rpb.name.isin([d.recap_panen for d in self.details]))
			)
		).run(as_dict=True)

		kontanan = [r.voucher_no for r in query if r.kontanan]
		non_kontanan = [r.voucher_no for r in query if not r.kontanan]

		errors = []

		if kontanan:
			e_kontanan = frappe.db.exists("Pengajuan Panen Kontanan", {
				"bkm_panen": ["in", kontanan], 
				"docstatus": 1
			})
			if e_kontanan:
				errors.append("Some harvests already have submitted Kontanan")

		if non_kontanan:
			p_payment = frappe.db.exists("Employee Payment Log", {
				"voucher_type": "Buku Kerja Mandor Panen",
				"voucher_no": ["in", non_kontanan], 
				"is_paid": 1
			})
			if p_payment:
				errors.append("Some harvests have already been paid")

		if errors:
			frappe.throw("<br>".join(errors))

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
			for field in ("", "_restan"):
				if recap := d.get(f"recap_panen{field}"):
					doc = frappe.get_doc("Recap Panen by Blok", recap)
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
			self.total_weight_internal = flt(self.out_weight_internal - self.in_weight_internal, self.precision("total_weight_internal"))
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
def get_recap_panen(blok, posting_date):
	filters = {
		"blok": blok, "posting_date": posting_date
	}

	recap_panen = frappe.get_value("Recap Panen by Blok", filters, [
		"name", "jumlah_janjang", "transfered_janjang"
	], as_dict=1)

	if not recap_panen:
		message = "Recap Panen by Blok not Found for Filters"
		for key, value in filters.items():
			message += f"<br>{unscrub(key)}: {value}"
			
		frappe.throw(message)
	
	ress = { 
		"recap_panen": recap_panen.name,
		"qty": flt(recap_panen.jumlah_janjang - recap_panen.transfered_janjang)
	}

	return ress