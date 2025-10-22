# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, get_url_to_form, now

from frappe.model.document import Document

class RekapTimbanganPanen(Document):
	def validate(self):
		self.get_bkm_panen()
		self.calculate_janjang()

	def get_bkm_panen(self):
		ret = get_bkm_panen(self.blok, self.panen_date)
		for fieldname, value in ret.items():
			if self.meta.get_field(fieldname) \
				and (
					value is not None or
					fieldname == "details"
				):				
				self.set(fieldname, value)

	def calculate_janjang(self):
		total_janjang = total_weight = 0.0
		for d in self.details:
			d.bjr = flt(d.total_weight / d.jumlah_janjang)
			total_janjang += d.jumlah_janjang
			total_weight += d.total_weight

		self.total_janjang = total_janjang
		self.total_weight = total_weight
		
		self.bjr = flt(self.total_weight / self.total_janjang)

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
			spb.workflow_state.as_("status"),
			spb.name.as_("surat_pengantar_buah"),
			spb_timbangan.panen_date.as_("spb_date"),
			spb.no_polisi,
			spb_timbangan.qty.as_("jumlah_janjang"),
			spb_timbangan.brondolan_qty.as_("total_brondolan"),
			spb.bjr,
			spb.total_weight,
			spb.netto_weight,
		)
		.where(
			(spb.docstatus == 1) &
			(spb_timbangan.bkm_panen == bkm["bkm_panen"])
		)
	).run(as_dict=True)

	if not rekap_timbangan:
		frappe.throw("Please create Surat Pengantar Buah First")

	details = []
	for rt in rekap_timbangan:
		if rt.status != "Weighed":
			frappe.throw(f"{get_url_to_form('Surat Pengantar Buah', rt.surat_pengantar_buah)} weight not verified")

		details.append({
			"surat_pengantar_buah": rt.surat_pengantar_buah,
			"spb_date": rt.spb_date,
			"no_polisi": rt.no_polisi,
			"jumlah_janjang": rt.jumlah_janjang,
			"total_brondolan": rt.total_brondolan,
			"bjr": rt.bjr,
			"total_weight": rt.total_weight,
			"netto_weight": rt.netto_weight,
		})

	ress = { 
		"buku_kerja_mandor_panen": bkm["bkm_panen"],
		"details": details
	}

	return ress