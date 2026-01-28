# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime
from sth.mill.doctype.tbs_ledger_entry.tbs_ledger_entry import create_tbs_ledger,reverse_tbs_ledger
from frappe import _
from frappe.model.mapper import get_mapped_doc

class Timbangan(Document):
	def validate(self):
		self.validate_ticket()
		if self.do_no and not self.storage:
			self.storage = frappe.get_doc("Delivery Order", self.do_no).items[0].warehouse


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

		elif self.type == "Dispatch":
			delivery_note = make_delivery_note(self.name)
			delivery_note.insert()
			delivery_note.submit()
			
			self.db_set('delivery_note', delivery_note.name)
			
			frappe.msgprint(
				msg=f"Delivery Note {delivery_note.name} has been created and submitted",
				title="Delivery Note Created",
				indicator="green"
			)

	def on_cancel(self):
		self.ignore_linked_doctypes = (
			"TBS Ledger Entry"
		)
		
		if self.type == "Receive":
			reverse_tbs_ledger(self.name)

	def validate_ticket(self):
		if frappe.db.exists("Timbangan",{"ticket_number": self.ticket_number,"docstatus":1}):
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

@frappe.whitelist()
def make_delivery_note(source_name, target_doc=None):
	
	def set_missing_values(source, target):
		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")
		if source.driver_name:
			# Cari driver berdasarkan driver_name
			driver = frappe.db.get_value('Driver', {'full_name': source.driver_name}, 'name')
			if driver:
				target.driver = driver
				target.driver_name = source.driver_name
		
		if source.transportir:
			# Cari transporter berdasarkan transportir
			transporter = frappe.db.get_value('Supplier', {'supplier_name': source.transportir, 'is_transporter': 1}, 'name')
			if transporter:
				target.transporter = transporter
				target.transporter_name = source.transportir
		
		# Set values from Delivery Order if do_no exists
		if source.do_no:
			do_doc = frappe.get_doc("Delivery Order", source.do_no)
			target.customer = do_doc.customer
			target.penandatangan = do_doc.penandatangan
			target.jabatan_penandatangan = do_doc.jabatan_penandatangan
			target.unit = do_doc.unit
			target.komoditi = do_doc.komoditi
			target.tempat_penyerahan = do_doc.tempat_penyerahan
			target.jenis_berikat = do_doc.jenis_berikat
			
			# Copy child table keterangan_per_komoditi
			if do_doc.keterangan_per_komoditi:
				for row in do_doc.keterangan_per_komoditi:
					target.append('keterangan_per_komoditi', {
						'parameter': row.parameter,
						'keterangan': row.keterangan
					})
	
	def update_item(source, target, source_parent):
		target.timbangan = source_parent.name
	
	doclist = get_mapped_doc(
		"Timbangan",
		source_name,
		{
			"Timbangan": {
				"doctype": "Delivery Note",
				"field_map": {
					"name": "timbangan_ref",
					"company": "company",
					"driver_name": "driver_name",
					"transportir": "transporter_name",
					"license_number": "lr_no", 
				}
			},
		},
		target_doc,
		set_missing_values
	)
	source_doc = frappe.get_doc("Timbangan", source_name)
	
	if source_doc.kode_barang and source_doc.netto:
		doclist.append('items', {
			'item_code': source_doc.kode_barang,
			'qty': source_doc.netto - (source_doc.potongan_sortasi / 100),
			'timbangan': source_doc.name
		})
	
	return doclist
@frappe.whitelist()
def make_purchase_receipt(source_name, target_doc=None):
	
	def set_missing_values(source, target):
		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")
	
	doclist = get_mapped_doc(
		"Timbangan",
		source_name,
		{
			"Timbangan": {
				"doctype": "Purchase Receipt",
				"field_map": {
					"name": "timbangan_ref", 
					"company": "company",
					"transportir": "transporter_name",
					"license_number": "lr_no",
				}
			},
		},
		target_doc,
		set_missing_values
	)
	
	source_doc = frappe.get_doc("Timbangan", source_name)
	
	if source_doc.kode_barang and source_doc.netto:
		doclist.append('items', {
			'item_code': source_doc.kode_barang,
			'qty': source_doc.netto - (source_doc.potongan_sortasi / 100),
			'timbangan': source_doc.name
		})
	
	return doclist