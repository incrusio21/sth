# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.utils import flt, now
from frappe.query_builder.custom import ConstantColumn
from frappe.model.document import Document

from sth.controllers.rencana_kerja_controller import get_tonase

class RencanaKerjaBulananSupervisiPanen(Document):
	def validate(self):
		self.get_tonase_divisi()

	def get_tonase_divisi(self):
		self.total_tonase = get_tonase(self.rencana_kerja_bulanan, {"divisi": self.divisi})
					
	def on_submit(self):
		self.update_rkb_panen()

	def on_cancel(self):
		self.update_rkb_panen()

	@frappe.whitelist()	
	def update_rkb_panen(self, cancel=0):
		if not cancel:
			rkb_panen = frappe.qb.DocType("Rencana Kerja Bulanan Panen")
			
			panen_list = (
				frappe.qb.from_(rkb_panen)
				.select(
					rkb_panen.name.as_("rencana_kerja_bulanan_panen"),
					rkb_panen.blok,
					rkb_panen.tonase
				)
				.where(
					(rkb_panen.docstatus == 1) &
					(rkb_panen.rencana_kerja_bulanan == self.rencana_kerja_bulanan) &
					(rkb_panen.divisi == self.divisi)
				)
			).run(as_dict=1)

			self.set("details", panen_list)
			self.update_child_table("details")

		for d in self.details:
			doc = frappe.get_doc("Rencana Kerja Bulanan Panen", d.rencana_kerja_bulanan_panen)
			doc.update_upah_supervisi(self)