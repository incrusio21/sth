# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

from frappe.model.document import Document

class RekapTimbanganPanen(Document):
	def validate(self):
		self.get_bkm_panen()
		self.calculate_janjang_brondolan()

	def get_bkm_panen(self):
		ret = get_bkm_panen(self.blok, self.panen_date)
		for fieldname, value in ret.items():
			if self.meta.get_field(fieldname) and value is not None:				
				self.set(fieldname, value)

	def calculate_janjang_brondolan(self):
		total_janjang = total_brondolan = netto_weight = 0.0
		for d in self.details:
			d.bjr = flt(d.netto_weight / d.jumlah_janjang)
			total_janjang += d.jumlah_janjang
			total_brondolan += d.total_brondolan
			netto_weight += d.netto_weight

		self.total_janjang = total_janjang
		self.total_brondolan = total_brondolan
		self.netto_weight = netto_weight
		self.total_weight = self.netto_weight + self.total_brondolan
		
		self.bjr = flt(self.netto_weight / self.total_janjang)

	def on_submit(self):
		self.update_transfered_bkm_panen()

	def on_cancel(self):
		self.update_transfered_bkm_panen()

	def update_transfered_bkm_panen(self):
		doc = frappe.get_doc("Buku Kerja Mandor Panen", self.buku_kerja_mandor_panen)
		doc.set_data_rekap_weight()


@frappe.whitelist()
def get_bkm_panen(blok, posting_date):
	from sth.plantation.doctype.surat_pengantar_buah.surat_pengantar_buah import get_bkm_panen

	bkm = get_bkm_panen(blok, posting_date)
	
	spb = frappe.qb.DocType("Surat Pengantar Buah")
	spb_timbangan = frappe.qb.DocType("SPB Timbangan Pabrik")

	rekap_timbangan = (
		frappe.qb.from_(spb)
		.inner_join(spb_timbangan)
		.on(spb.name == spb_timbangan.parent)
		.select(
			spb.name.as_("surat_pengantar_buah"),
			spb_timbangan.panen_date.as_("spb_date"),
			spb.no_polisi,
			spb_timbangan.qty.as_("jumlah_janjang"),
			spb_timbangan.brondolan_qty.as_("total_brondolan"),
			spb_timbangan.total_weight,
			spb_timbangan.netto_weight,
		)
		.where(
			(spb.docstatus == 1) &
			(spb_timbangan.bkm_panen == bkm["bkm_panen"])
		)
	).run(as_dict=1)

	ress = { 
		"buku_kerja_mandor_panen": bkm["bkm_panen"],
		"details": rekap_timbangan
	}

	return ress