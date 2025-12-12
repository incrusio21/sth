# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder.functions import Coalesce, Sum
from frappe.utils import flt


class RecapPanenbyBlok(Document):
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
			frappe.throw("Transfered Janjang exceeds limit.")

		self.db_update()

	def on_trash(self):
		self.remove_document()

	def remove_document(self):
		# skip jika berasal dari transaksi
		if self.flags.transaction_panen:
			return
		
		msg = _("Individual Recap Panen by Blok cannot be deleted.")
		msg += "<br>" + _("Please cancel related transaction.")
		frappe.throw(msg)

def on_doctype_update():
	frappe.db.add_unique("Recap Panen by Blok", ["blok", "company", "posting_date"], constraint_name="unique_blok_company") 