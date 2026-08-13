# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder.functions import Coalesce, Sum
from frappe.utils import flt, format_date, get_link_to_form

class RecapPanenbyBlok(Document):
	def validate(self):
		self.calculate_total_janjang()

	def calculate_total_janjang(self):
		self.jumlah_janjang = self.jumlah_brondolan = 0
		same_voucher = {}
		unique_recap = []
		for vc in self.voucher_recap:
			key = (vc.voucher_type, vc.voucher_no)
			existing = same_voucher.get(key)
			if existing:
				# voucher yang sama sudah ada di tabel: pakai nilai terakhir,
				# jangan dihitung dobel
				existing.jumlah_janjang = vc.jumlah_janjang
				existing.jumlah_brondolan = vc.jumlah_brondolan
				continue

			same_voucher[key] = vc
			unique_recap.append(vc)

		for idx, vc in enumerate(unique_recap, start=1):
			vc.idx = idx
			self.jumlah_janjang += vc.jumlah_janjang
			self.jumlah_brondolan += vc.jumlah_brondolan

		self.voucher_recap = unique_recap

	def on_trash(self):
		self.remove_document()

	def remove_document(self):
		# skip jika berasal dari transaksi
		if self.flags.transaction_panen:
			return

		# if frappe.flags.mass_delete_bkm:
		# 	return
		
		msg = _("Individual Recap Panen by Blok cannot be deleted.")
		msg += "<br>" + _("Please cancel related transaction.")
		frappe.throw(msg)

	def calculate_transfered_weight(self):
		spb = frappe.qb.DocType("SPB Timbangan Pabrik")

		transfered_janjang = (
			frappe.qb.from_(spb)
			.select(
				Coalesce(Sum(spb.qty), 0)
            )
			.where(
                (spb.docstatus == 1) &
                (spb.recap_panen == self.name)
			)
		).run()[0][0]

		transfered_restan = (
			frappe.qb.from_(spb)
			.select(
				Coalesce(Sum(spb.qty_restan), 0), 
            )
			.where(
                (spb.docstatus == 1) &
                (spb.recap_panen_restan == self.name)
			)
		).run()[0][0]

		self.transfered_janjang = flt(transfered_janjang + transfered_restan, self.precision("transfered_janjang"))

		if self.transfered_janjang > self.jumlah_janjang:
			frappe.throw(self.get_transfered_exceed_message())

		self.db_update()

	def get_transfered_exceed_message(self):
		"""Pesan kelebihan transfer beserta rincian SPB penyumbangnya.

		Tanpa angkanya orang harus buka rekap lalu menyisir SPB satu per satu
		untuk tahu mana yang kelewat, padahal datanya sudah ada di tangan waktu
		throw terjadi.
		"""
		presisi = self.precision("transfered_janjang")
		lebih = flt(self.transfered_janjang - self.jumlah_janjang, presisi)

		msg = _("Transfered Janjang for Blok {0} in {1} exceeds the limit.").format(
			self.blok, format_date(self.posting_date)
		)
		msg += "<br>" + _("Janjang panen {0}, terkirim {1}, lebih {2}.").format(
			flt(self.jumlah_janjang, presisi), flt(self.transfered_janjang, presisi), lebih
		)

		rincian = frappe.db.sql(
			"""
			SELECT parent,
				SUM(CASE WHEN recap_panen = %(recap)s THEN qty ELSE 0 END) AS qty,
				SUM(CASE WHEN recap_panen_restan = %(recap)s THEN qty_restan ELSE 0 END) AS qty_restan
			FROM `tabSPB Timbangan Pabrik`
			WHERE parenttype = 'Surat Pengantar Buah'
				AND docstatus = 1
				AND (recap_panen = %(recap)s OR recap_panen_restan = %(recap)s)
			GROUP BY parent
			ORDER BY parent
			""",
			{"recap": self.name},
			as_dict=True,
		)

		if not rincian:
			return msg

		msg += "<br><br>" + _("Rincian pengiriman:")
		for r in rincian[:20]:
			baris = f"<br>{get_link_to_form('Surat Pengantar Buah', r.parent)}: {flt(r.qty, presisi)}"
			if flt(r.qty_restan):
				baris += _(" + {0} restan").format(flt(r.qty_restan, presisi))

			msg += baris

		if len(rincian) > 20:
			msg += "<br>" + _("dan {0} SPB lainnya.").format(len(rincian) - 20)

		return msg

	def set_data_rekap_weight(self):
		rtp = frappe.qb.DocType("Timbangan Panen Details")

		self.total_weight = (
			frappe.qb.from_(rtp)
			.select(
				Coalesce(Sum(rtp.total_weight), 0)
            )
			.where(
                (rtp.docstatus == 1) &
                (rtp.recap_panen == self.name)
			)
		).run()[0][0]

		self.bjr = flt(self.total_weight / self.jumlah_janjang)
		self.save()

def on_doctype_update():
	frappe.db.add_unique("Recap Panen by Blok", ["blok", "company", "posting_date"], constraint_name="unique_blok_company") 