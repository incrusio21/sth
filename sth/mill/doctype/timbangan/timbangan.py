# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe,copy
from frappe.utils import add_days
from frappe.model.document import Document
from frappe.utils import get_datetime,flt
from sth.mill.doctype.tbs_ledger_entry.tbs_ledger_entry import create_tbs_ledger,reverse_tbs_ledger,repost_qty_tbs
from frappe import _, delete_doc
from frappe.model.mapper import get_mapped_doc

class Timbangan(Document):

	def before_insert(self):
		# API sering kirim docstatus 1 langsung saat insert. Kalau dibiarkan,
		# Frappe hanya menulis docstatus=1 ke DB tanpa menjalankan lifecycle
		# submit (before_submit/on_submit tidak terpanggil). Jadi paksa masuk
		# sebagai draft dulu, lalu submit ulang secara eksplisit di after_insert.
		if self.owner and "api@sth" in self.owner and self.docstatus == 1:
			self.flags.submit_after_insert = True
			self.docstatus = 0

	def after_insert(self):
		if self.flags.get("submit_after_insert"):
			self.submit()

	def validate(self):
		# self.validate_ticket()
		self.map_api_ticket_number()
		self.validate_qty_do()

		if self.do_no and not self.storage:
			self.storage = frappe.get_doc("Delivery Order", self.do_no).items[0].warehouse

		if self.company:
			unit = frappe.db.sql(""" SELECT name, company FROM `tabUnit` WHERE mill = 1 """,as_dict=1)
			for row in unit:
				if row.company == self.company:
					self.unit = row.name
	
	def make_dn(self):
		if self.type == "Dispatch":
			self.create_delivery_notes()

	def on_submit(self):
		if self.type == "Receive" and self.receive_type != "Lain - Lain":
			self.make_tbs_ledger()
		elif self.type == "Dispatch":
			self.create_delivery_notes()
		if self.receive_type == "TBS Internal":
			if self.spb:
				spb_doc = frappe.get_doc("Surat Pengantar Buah", self.spb)
				spb_doc.in_weight = self.bruto
				spb_doc.out_weight = self.tara
				spb_doc.total_weight = self.netto
				spb_doc.in_time = self.weight_in_time
				spb_doc.out_time = self.weight_out_time
				spb_doc.workflow_state = "Weighed"
				spb_doc.bjr = spb_doc.total_weight / spb_doc.total_janjang
				for row in spb_doc.details:
					row.total_weight = self.netto
					row.db_update()
				spb_doc.db_update()

	def on_cancel(self):
		self.ignore_linked_doctypes = (
			"TBS Ledger Entry",
			"Sortasi"
		)
		
		if self.type == "Receive":
			reverse_tbs_ledger(self.name)
			# repost_qty_tbs(self.kode_barang,add_days(self.posting_date,-7))
			repost_qty_tbs(
				from_date=add_days(self.posting_date,-7),
				item_code=self.kode_barang
			)
		
		if sort_doc:=frappe.db.get_value("Sortasi",{"no_timbangan": self.name}):
			frappe.get_doc("Sortasi",sort_doc).cancel()

	def map_api_ticket_number(self):
		if self.owner and "api@sth" in self.owner and self.trans_no == self.ticket_number:
			self.api_ticket_number = self.spb
			self.ticket_number = ""
			spb_name = frappe.db.get_value("Surat Pengantar Buah", {"trans_no": self.api_ticket_number}, "name")
			self.spb = spb_name or ""

			if self.type == "Wb Pabrik":
				self.type = "Receive"
				self.receive_type = "TBS Internal" 
				self.jumlah_janjang = self.total_janjang

	def validate_ticket(self):
		if frappe.db.exists("Timbangan",{"ticket_number": self.ticket_number,"docstatus":1}):
			frappe.throw("Ticket has been used before")
	
	def validate_qty_do(self):
		if not self.do_no:
			self.qty_do = 0
			self.qty_do_2 = 0
			return

		sisa_do_1 = self.get_sisa_do_available(self.do_no)
		self.qty_do = min(flt(self.netto_2), sisa_do_1)
		remaining = flt(self.netto_2) - self.qty_do

		if remaining > 0:
			if not self.no_do_2:
				frappe.throw(f"Jumlah Netto melebihi qty DO {self.do_no} (sisa: {sisa_do_1}). Isi Delivery Order No 2 untuk menampung kelebihannya.")

			sisa_do_2 = self.get_sisa_do_available(self.no_do_2)
			if remaining > sisa_do_2:
				frappe.throw(f"Jumlah Netto melebihi qty DO {self.do_no} dan {self.no_do_2}. Kelebihan: {remaining - sisa_do_2}")

			self.qty_do_2 = remaining
		else:
			self.qty_do_2 = 0

	def get_sisa_do_available(self, do_no):
		qty_do = frappe.db.get_value("Delivery Order Item",{"item_code":self.kode_barang,"parent": do_no},["qty"])
		qty_timbangan = frappe.db.get_value("Timbangan",filters={"do_no":do_no,"name":["!=",self.name],"kode_barang": self.kode_barang,"docstatus":["!=",2]},fieldname=["sum(netto_2) as qty"])
		qty_timbangan_2 = frappe.db.get_value("Timbangan",filters={"no_do_2":do_no,"name":["!=",self.name],"kode_barang": self.kode_barang,"docstatus":["!=",2]},fieldname=["sum(qty_do_2) as qty"])
		return flt(qty_do) - flt(qty_timbangan) - flt(qty_timbangan_2)

	def create_delivery_notes(self):
		dn_names = []

		dn1 = make_delivery_note(self.name, do_no=self.do_no, qty=self.qty_do or self.netto_2)
		dn1.insert()
		dn1.submit()
		self.db_set('delivery_note', dn1.name)
		dn_names.append(dn1.name)

		if self.no_do_2 and flt(self.qty_do_2) > 0:
			dn2 = make_delivery_note(self.name, do_no=self.no_do_2, qty=self.qty_do_2)
			dn2.insert()
			dn2.submit()
			self.db_set('delivery_note_2', dn2.name)
			dn_names.append(dn2.name)

		frappe.msgprint(
			msg=f"Delivery Note {', '.join(dn_names)} has been created and submitted",
			title="Delivery Note Created",
			indicator="green"
		)

	def make_tbs_ledger(self):
		create_tbs_ledger(frappe._dict({
			"item_code": self.kode_barang,
			"posting_date": self.posting_date,
			"posting_time" : self.posting_time,
			"posting_datetime": get_datetime(f"{self.posting_date} {self.posting_time}"),
			"type": self.receive_type,
			"voucher_type": self.doctype,
			"voucher_no": self.name,
			"balance_qty": self.netto_2,
		}))


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
@frappe.validate_and_sanitize_search_inputs
def get_spb_available(doctype, txt, searchfield, start, page_len, filters):
	params = {
		"txt": f"%{txt}%",
		"start": start,
		"page_len": page_len
	}
	return frappe.db.sql("""
		select spb.name,spb.pabrik,spb.no_polisi 
		from `tabSurat Pengantar Buah` spb
		join `tabSecurity Check Point` scp on scp.spb = spb.name
		where spb.name LIKE %(txt)s AND scp.docstatus = 1 
		group by spb.name
		LIMIT %(start)s, %(page_len)s
	""",params)
	
@frappe.whitelist()
def make_delivery_note(source_name, do_no=None, qty=None, target_doc=None):

	def set_missing_values(source, target):
		target.set_posting_time = 1
		effective_do_no = do_no or source.do_no

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

		# Set values from Delivery Order if effective_do_no exists
		if effective_do_no:
			do_doc = frappe.get_doc("Delivery Order", effective_do_no)
			target.delivery_order = effective_do_no
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

			if source.kode_barang and source.netto:
				fields_to_remove = ["doctype", "name", "owner","creation", "modified", "modified_by","idx"]
				item = next((r for r in do_doc.items if r.item_code == source.kode_barang),[])
				new_item = copy.deepcopy(item)
				new_item = new_item.as_dict()
				new_item.qty = flt(qty) if qty is not None else source.netto_2
				new_item.timbangan = source.name
				new_item.delivery_order_item = item.name

				for f in fields_to_remove:
					new_item.pop(f, None)

				target.append("items",new_item)

		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")


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
					"do_no": "delivery_order"
				}
			},
		},
		target_doc,
		set_missing_values
	)

	for row in doclist.items:
		if row.item_code:
			item_doc = frappe.get_doc("Item", row.item_code)
			for row_item in item_doc.item_defaults:
				if row_item.company == doclist.company:
					row.warehouse = row_item.default_warehouse
	
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
			'qty': source_doc.netto_2,
			'timbangan': source_doc.name
		})
	
	return doclist

@frappe.whitelist()
def get_timbangan_settings():
	return frappe.db.get_all('Timbangan Setting Detail',['location','baudrate','baudrate','databits','parity','stopbits'])

@frappe.whitelist()
def get_sisa_do(reference):
	delivered,qty = frappe.db.get_value("Delivery Order Item",reference,["delivered_qty","qty"])
	return flt(qty) - flt(delivered)

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_do_2_available(doctype, txt, searchfield, start, page_len, filters):
	do_no = filters.get("do_no")
	kode_barang = filters.get("kode_barang")
	customer = frappe.db.get_value("Delivery Order", do_no, "customer") if do_no else None

	conditions = ["do.name LIKE %(txt)s", "do.docstatus = 1"]
	params = {"txt": f"%{txt}%", "start": start, "page_len": page_len}

	if customer:
		conditions.append("do.customer = %(customer)s")
		params["customer"] = customer
	if kode_barang:
		conditions.append("doi.item_code = %(kode_barang)s")
		params["kode_barang"] = kode_barang
	if do_no:
		conditions.append("do.name != %(do_no)s")
		params["do_no"] = do_no

	return frappe.db.sql(f"""
		select do.name, do.customer
		from `tabDelivery Order` do
		join `tabDelivery Order Item` doi on doi.parent = do.name
		where {" and ".join(conditions)}
		group by do.name
		limit %(start)s, %(page_len)s
	""", params)

@frappe.whitelist()
def get_sisa_do_2(do_no, item_code):
	item = frappe.db.get_value("Delivery Order Item", {"parent": do_no, "item_code": item_code}, ["delivered_qty", "qty"], as_dict=True)
	if not item:
		return 0
	return flt(item.qty) - flt(item.delivered_qty)