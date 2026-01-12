# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime
from sth.mill.doctype.tbs_ledger_entry.tbs_ledger_entry import create_tbs_ledger,reverse_tbs_ledger

class Timbangan(Document):
	def validate(self):
		self.validate_ticket()

	def on_submit(self):
		if self.type == "Receive":
			create_tbs_ledger(frappe._dict({
				"item_code": self.kode_barang,
				"posting_date": self.posting_date,
				"posting_time" : self.posting_time,
				"posting_datetime": get_datetime(f"{self.posting_date} {self.posting_time}"),
				"type": self.receive_type,
				"voucher_type": self.doctype,
				"voucher_no": self.name,
				"balance_qty": self.netto - (self.potongan_sortasi/100),
			}))

	def on_cancel(self):
		self.ignore_linked_doctypes = (
			"TBS Ledger Entry"
		)
		
		if self.type == "Receive":
			reverse_tbs_ledger(self.name)

	def validate_ticket(self):
		if frappe.db.exist("Timbangan",{"ticket_number": self.ticket_number,"docstatus":1}):
			frappe.throw("Ticket has been used before")

@frappe.whitelist()
def get_spb_detail(spb):
	spb_details = frappe.db.sql("""
		select stp.blok,b.tahun_tanam, stp.qty as jumlah_janjang, b.unit, b.divisi, stp.total_janjang 
		from `tabSPB Timbangan Pabrik` stp
		join `tabBlok` b on b.name = stp.blok
		where stp.parent = %s
	""",[spb],as_dict=True)

	return spb_details