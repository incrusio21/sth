# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, get_url_to_form, now

from frappe.model.document import Document

from sth.utils import generate_duplicate_key
from sth.plantation.doctype.surat_pengantar_buah.surat_pengantar_buah import get_recap_panen

class RekapTimbanganPanen(Document):
	def validate(self):
		self.calculate_janjang()

	
	def calculate_janjang(self):
		total_janjang = total_weight = 0.0
		for d in self.details:
			d.bjr = flt(d.total_weight / d.jumlah_janjang) if d.jumlah_janjang else 0
			total_janjang += d.jumlah_janjang
			total_weight += d.total_weight

		self.total_janjang = total_janjang
		self.total_weight = total_weight
		
		self.bjr = flt(self.total_weight / self.total_janjang)

	def before_submit(self):
		generate_duplicate_key(self, "duplicate_key", [self.company, self.unit, self.divisi, self.transaction_date])
	
	def on_submit(self):
		self.update_transfered_bkm_panen()

	def before_cancel(self):
		generate_duplicate_key(self, "duplicate_key", cancel=1)

	def on_cancel(self):
		# if frappe.flags.mass_delete_bkm:
		# 	return
		
		self.update_transfered_bkm_panen()
		
	def update_transfered_bkm_panen(self):
		# Baris yang recap-nya tidak ketemu tetap boleh ikut direkap — janjangnya
		# cuma belum bisa dipulangkan ke BKM. Tanpa disaring, None-nya sampai ke
		# frappe.get_doc dan menggagalkan seluruh submit.
		list_rb = set(rp.recap_panen for rp in self.details if rp.recap_panen)

		voucher_data = {}
		for rb in list_rb:
			doc = frappe.get_doc("Recap Panen by Blok", rb)
			doc.set_data_rekap_weight()

			for vc in doc.voucher_recap:
				voucher_data.setdefault(
					(vc.voucher_type, vc.voucher_no), {}
				).setdefault(doc.blok, doc.bjr)

		for (v_type, v_no), blok in voucher_data.items():
			voucher_obj = frappe.get_doc(v_type, v_no)
			voucher_obj.update_hasil_kerja_bjr(blok)

@frappe.whitelist()
def get_bkm_panen(unit, divisi, posting_date):
	spb = frappe.qb.DocType("Surat Pengantar Buah")
	spb_timbangan = frappe.qb.DocType("SPB Timbangan Pabrik")

	rekap_timbangan = (
		frappe.qb.from_(spb)
		.inner_join(spb_timbangan)
		.on(spb.name == spb_timbangan.parent)
		.select(
			spb.workflow_state.as_("status"),
			spb.name.as_("surat_pengantar_buah"),
			spb.posting_date,
			spb.no_polisi,
			spb_timbangan.blok,
			spb_timbangan.panen_date,
			spb_timbangan.total_janjang.as_("jumlah_janjang"),
			spb_timbangan.total_weight,
			spb_timbangan.recap_panen,
			spb.bjr,
		)
		.where(
			(spb.docstatus == 1) &
			(spb.unit == unit) &
			(spb.divisi == divisi) &
			(spb.posting_date == posting_date)
		)
	).run(as_dict=True)

	if not rekap_timbangan:
		frappe.throw("Please create Surat Pengantar Buah First")

	details = []
	for rt in rekap_timbangan:
		if rt.status != "Weighed":
			frappe.throw(f"{get_url_to_form('Surat Pengantar Buah', rt.surat_pengantar_buah)} weight not verified")

		# Jaring pengaman untuk baris SPB yang tautannya tidak pernah terpasang:
		# recap-nya lahir sesudah SPB tersimpan, dan sebelum BKM Panen ikut
		# menyusulkan tautannya tidak ada yang mengisi kolom itu. Dicari lagi di
		# sini supaya rekapnya tidak lahir dengan recap_panen kosong — tanpa itu
		# janjangnya tidak pernah pulang ke BKM.
		if not rt.recap_panen:
			rt.recap_panen = get_recap_panen(rt.blok, rt.panen_date).get("recap_panen")

		details.append(rt)

	ress = { 
		"details": details
	}

	return ress