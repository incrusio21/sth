# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe,copy,random
from frappe.utils import add_days
from frappe.model.document import Document
from frappe.utils import get_datetime,flt
from sth.mill.doctype.tbs_ledger_entry.tbs_ledger_entry import create_tbs_ledger,reverse_tbs_ledger,repost_qty_tbs
from sth.mill.doctype.data_tbs.data_tbs import hitung_ulang_setelah_timbangan
from sth.custom.api import submit_after_insert
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

	def generate_trans_no(self):
		while True:
			trans_no = "TMBTML" + "".join(str(random.randint(0, 9)) for _ in range(18))
			if not frappe.db.exists("Timbangan", {"trans_no": trans_no}):
				return trans_no

	def after_insert(self):
		if not self.trans_no:
			# self.trans_no = self.generate_trans_no()
			self.trans_no = self.name
			self.db_update()

		elif self.flags.get("submit_after_insert"):
			submit_after_insert(self)

	def validate(self):
		# self.validate_ticket()
		self.map_api_ticket_number()
		self.set_data_dari_po()
		self.validate_qty_do()
		self.hitung_netto()

		if self.do_no and not self.storage:
			self.storage = frappe.get_doc("Delivery Order", self.do_no).items[0].warehouse

		if self.company:
			unit = frappe.db.sql(""" SELECT name, company FROM `tabUnit` WHERE mill = 1 """,as_dict=1)
			for row in unit:
				if row.company == self.company:
					self.unit = row.name
	
	def set_data_dari_po(self):
		"""Isi kode_barang dan supplier dari PO untuk Receive "Lain - Lain".

		Receive jenis ini tidak lewat SPB maupun DO, jadi Security Check Point
		tidak pernah mengisi items_do dan fetch_from ticket_number.items_do di
		kode_barang tidak menghasilkan apa-apa. PO-nya satu-satunya yang tahu
		barang apa yang masuk.

		Hanya PO berisi satu barang yang diisikan sendiri; kalau lebih, barangnya
		dibiarkan dipilih operator supaya yang ditimbang tidak ditebak. Yang sudah
		terisi tidak ditimpa — timbangan yang dibuat lewat UI sudah mengisinya
		duluan, termasuk pilihan operator untuk PO berbaris banyak.
		"""
		if self.receive_type != "Lain - Lain" or not self.purchase_order:
			return

		# Supplier "Lain - Lain" tidak datang dari QR supir seperti TBS Eksternal;
		# yang mengikat siapa pemasoknya cuma PO-nya. Tanpa ini Purchase Receipt
		# yang dibuat dari timbangan lahir tanpa supplier.
		if not self.supplier:
			self.supplier = frappe.db.get_value("Purchase Order", self.purchase_order, "supplier")

		if self.kode_barang:
			return

		items = get_item_purchase_order_list(self.purchase_order)
		if len(items) != 1:
			return

		self.kode_barang = items[0]
		# fetch_from kode_barang.item_name sudah lewat waktu validate dijalankan,
		# jadi nama barangnya ikut diisi di sini supaya tidak baru muncul di
		# penyimpanan berikutnya.
		self.nama_barang = frappe.db.get_value("Item", self.kode_barang, "item_name")

	def make_dn(self):
		if self.type == "Dispatch":
			self.create_delivery_notes()

	def hitung_netto(self):
		"""Isi netto dan netto_2 dari bruto dan tara.

		Kembaran calculate_weight di timbangan.js. Selama ini rumusnya cuma ada
		di form, jadi dokumen yang masuk lewat API atau import tersimpan dengan
		netto apa adanya — nol kalau pengirimnya tidak ikut mengisi — dan angka
		itulah yang dibaca Data TBS, SPB, sampai stok.

		Baru dihitung kalau bruto dan tara dua-duanya terisi. Truk ditimbang dua
		kali, dan di antara keduanya salah satu masih nol; menghitung netto di
		saat itu cuma menghasilkan berat truk penuh yang terlihat seperti muatan
		— persis yang terjadi pada timbangan yang taranya tidak pernah diambil.
		"""
		if not (flt(self.bruto) and flt(self.tara)):
			self.netto = 0
			self.netto_2 = 0
			return

		self.netto = flt(self.bruto) - flt(self.tara)
		self.netto_2 = self.netto - (self.netto * flt(self.potongan_sortasi) / 100)

	def before_submit(self):
		self.validate_berat()

	def validate_berat(self):
		"""Bruto dan tara dua-duanya harus sudah ditimbang sebelum disubmit.

		Netto lahir dari selisih keduanya, dan netto itu yang mengalir ke Data
		TBS, SPB, Purchase Receipt, dan stok. Salah satu yang masih nol membuat
		seluruh rantai itu memakai angka yang terlalu besar, dan membetulkannya
		belakangan jauh lebih mahal daripada berhenti di sini.
		"""
		kosong = [nama for nilai, nama in ((self.bruto, "Bruto"), (self.tara, "Tara")) if not flt(nilai)]

		if not kosong:
			return

		frappe.throw(
			_("{0} masih nol. Timbangan tidak bisa disubmit sebelum keduanya ditimbang.").format(
				frappe.bold(" dan ".join(kosong))
			)
		)

	def on_submit(self):
		if self.type == "Receive" and self.receive_type != "Lain - Lain":
			self.make_tbs_ledger()
		elif self.type == "Dispatch":
			self.create_delivery_notes()
		if self.receive_type == "TBS Internal":
			self.update_spb_weight()

		hitung_ulang_setelah_timbangan(self)

	def update_spb_weight(self):
		"""Salin hasil timbang ke SPB.

		Dipisah dari on_submit supaya bisa dipanggil ulang saat janjang di SPB
		berubah sesudah timbangan disubmit (lihat create_or_update di Surat
		Pengantar Buah) — tanpa ikut menjalankan lagi make_tbs_ledger yang akan
		menggandakan TBS Ledger Entry.
		"""
		if not self.spb:
			return

		spb_doc = frappe.get_doc("Surat Pengantar Buah", self.spb)
		spb_doc.in_weight = self.bruto
		spb_doc.out_weight = self.tara
		spb_doc.total_weight = self.netto or self.bruto - self.tara
		spb_doc.in_time = self.weight_in_time
		spb_doc.out_time = self.weight_out_time
		spb_doc.workflow_state = "Weighed"
		# SPB yang dibuat otomatis dari Security Check Point belum punya detail
		# blok, jadi total_janjang-nya masih 0 saat ditimbang
		spb_doc.bjr = flt(spb_doc.total_weight / spb_doc.total_janjang) if spb_doc.total_janjang else 0

		# netto dibagi menurut persentase tiap baris, bukan disalin utuh ke semua
		# baris. dulu tiap baris membawa netto penuh, jadi dua baris blok yang sama
		# sama-sama terhitung sebesar satu truk
		spb_doc.bagi_berat_ke_baris(spb_doc.total_weight)

		for row in spb_doc.details:
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

		hitung_ulang_setelah_timbangan(self)

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
			self.sisa_do = 0
			self.sisa_do_2 = 0
			return

		# Sisa DO dihitung ulang tiap simpan. Dulu kedua field ini cuma diisi JS
		# waktu reference_do_item atau no_do_2 diubah, jadi angkanya berhenti di
		# keadaan saat timbangannya dibuat — dan tidak pernah ikut turun waktu
		# Delivery Note lain memakan DO yang sama. Yang menulis ulang sesudah DN
		# ada: perbarui_sisa_do_timbangan, dipanggil dari hook Delivery Note.
		self.sisa_do = format_sisa(hitung_sisa_do(self.do_no, self.kode_barang))
		if self.no_do_2:
			self.sisa_do_2 = format_sisa(hitung_sisa_do(self.no_do_2, self.kode_barang))
		else:
			self.sisa_do_2 = 0

		# dilantai di 0: sisa DO 1 bisa minus kalau timbangan lain sudah memakannya
		# lebih dari qty DO-nya. Tanpa ini qty_do ikut minus, dan DN DO 1 dibuat
		# dengan qty negatif sehingga submit-nya ditolak.
		sisa_do_1 = max(0.0, self.get_sisa_do_available(self.do_no))
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
		"""Sisa qty DO yang belum dibebani timbangan lain (draft ikut dihitung)."""
		qty_do = frappe.db.get_value("Delivery Order Item",{"item_code":self.kode_barang,"parent": do_no},["qty"])

		# Yang dibebankan timbangan lain ke DO 1 bukan netto penuhnya melainkan
		# qty_do — sisanya ditampung DO 2. Dulu yang dijumlahkan netto_2, jadi
		# tiap timbangan yang terbelah ke dua DO terhitung memakan DO 1 sebesar
		# netto penuh dan sisa DO 1 bisa jadi minus.
		#
		# Yang tidak memakai DO 2 tetap dihitung senetto_2-nya: itu yang dipakai
		# create_delivery_notes, sekaligus menutup timbangan lama dari sebelum ada
		# fitur dua DO yang qty_do-nya tidak pernah terisi.
		qty_timbangan = frappe.db.sql("""
			SELECT SUM(CASE WHEN COALESCE(no_do_2, '') = '' THEN COALESCE(netto_2, 0)
						   ELSE COALESCE(qty_do, 0) END)
			FROM `tabTimbangan`
			WHERE do_no = %(do_no)s
			  AND name != %(name)s
			  AND kode_barang = %(kode_barang)s
			  AND docstatus != 2
		""", {"do_no": do_no, "name": self.name or "", "kode_barang": self.kode_barang})[0][0]

		qty_timbangan_2 = frappe.db.get_value("Timbangan",filters={"no_do_2":do_no,"name":["!=",self.name],"kode_barang": self.kode_barang,"docstatus":["!=",2]},fieldname=["sum(qty_do_2) as qty"])
		return flt(qty_do) - flt(qty_timbangan) - flt(qty_timbangan_2)

	def create_delivery_notes(self):
		dn_names = []

		# qty_do 0 berarti DO 1 sudah habis dan seluruh netto ditampung DO 2, jadi
		# DN untuk DO 1 tidak dibuat sama sekali. Fallback ke netto_2 cuma untuk
		# timbangan yang tidak memakai DO 2.
		if flt(self.qty_do) > 0 or not self.no_do_2:
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
					# posting_date tidak ikut tersalin sendiri karena no_copy, jadi
					# disebut di sini: DN mengikuti tanggal timbangannya, bukan tanggal
					# DN itu dibuat. set_posting_time di set_missing_values yang menjaga
					# validate_posting_time tidak menimpanya lagi dengan hari ini.
					"posting_date": "posting_date",
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
					# supplier ikut dipetakan supaya set_missing_values di atas sudah
					# melihatnya; kalau baru diisi sesudah get_mapped_doc, alamat dan
					# kontak supplier tidak ikut terisi.
					"supplier": "supplier",
				}
			},
		},
		target_doc,
		set_missing_values
	)
	
	source_doc = frappe.get_doc("Timbangan", source_name)
	
	if source_doc.kode_barang and source_doc.netto:
		baris = {
			'item_code': source_doc.kode_barang,
			'qty': source_doc.netto_2,
			'timbangan': source_doc.name
		}
		baris.update(get_referensi_po(source_doc))
		doclist.append('items', baris)
	
	return doclist


def get_referensi_po(source_doc):
	"""Kolom baris Purchase Receipt yang mengikatnya ke baris PO.

	Tanpa purchase_order_item, Purchase Receipt tidak pernah menutup PO-nya:
	received_qty di baris PO tetap 0 dan PO-nya menggantung "To Receive and Bill"
	selamanya, padahal barangnya sudah ditimbang masuk.

	qty timbangan selalu kilogram hasil jembatan, jadi satuannya dipaksa ke stock
	uom barangnya dengan conversion factor 1 dan harga PO dibagi conversion factor
	baris PO supaya nilainya tetap sama biarpun PO-nya dipesan dalam satuan lain.
	"""
	if not source_doc.purchase_order or not source_doc.kode_barang:
		return {}

	baris_po = get_baris_purchase_order(source_doc.purchase_order, source_doc.kode_barang)
	if not baris_po:
		return {}

	conversion_factor = flt(baris_po.conversion_factor) or 1

	return {
		"purchase_order": source_doc.purchase_order,
		"purchase_order_item": baris_po.name,
		"uom": baris_po.stock_uom,
		"stock_uom": baris_po.stock_uom,
		"conversion_factor": 1,
		"rate": flt(baris_po.rate) / conversion_factor,
		"warehouse": baris_po.warehouse,
	}


def get_baris_purchase_order(purchase_order, item_code):
	"""Baris PO yang dipakai baris Purchase Receipt untuk barang ini.

	Baris yang belum penuh didahulukan supaya penerimaan berikutnya tidak
	menumpuk di baris yang sudah tertutup. Kalau semua barisnya sudah penuh,
	baris pertama yang dipakai: kelebihannya lebih baik tetap menempel di PO —
	dan kena batas over receipt ERPNext — ketimbang masuk tanpa PO sama sekali.
	"""
	rows = frappe.db.sql("""
		select name, qty, received_qty, rate, uom, stock_uom, conversion_factor, warehouse
		from `tabPurchase Order Item`
		where parent = %(purchase_order)s and item_code = %(item_code)s
		order by idx
	""", {"purchase_order": purchase_order, "item_code": item_code}, as_dict=True)

	if not rows:
		return None

	for row in rows:
		if flt(row.received_qty) < flt(row.qty):
			return row

	return rows[0]

@frappe.whitelist()
def get_timbangan_settings():
	return frappe.db.get_all('Timbangan Setting Detail',['location','baudrate','baudrate','databits','parity','stopbits'])

@frappe.whitelist()
def get_sisa_do(reference):
	delivered,qty = frappe.db.get_value("Delivery Order Item",reference,["delivered_qty","qty"])
	return flt(qty) - flt(delivered)


def hitung_sisa_do(do_no, item_code):
	"""Sisa DO menurut Delivery Note: qty barisnya dikurangi yang sudah terkirim."""
	if not do_no or not item_code:
		return 0

	item = frappe.db.get_value(
		"Delivery Order Item",
		{"parent": do_no, "item_code": item_code},
		["qty", "delivered_qty"],
		as_dict=True,
	)
	if not item:
		return 0

	return flt(item.qty) - flt(item.delivered_qty)


def format_sisa(nilai):
	"""sisa_do dan sisa_do_2 fieldtype-nya Data, jadi angkanya disimpan sebagai
	teks. Yang bulat ditulis tanpa ".0" supaya bentuknya sama dengan yang selama
	ini ditulis JS."""
	nilai = flt(nilai)
	return int(nilai) if nilai == int(nilai) else nilai


def perbarui_sisa_do_timbangan(do_no, item_code):
	"""Tulis ulang Sisa DO di semua Timbangan yang memakai DO dan barang ini.

	Dipanggil sesudah Delivery Note mengubah delivered_qty. Tanpa ini angkanya
	cuma potret saat timbangannya dibuat: DN berikutnya yang memakan DO yang
	sama tidak pernah ikut menurunkannya, padahal field-nya ikut tampil di
	preview list.
	"""
	if not do_no or not item_code:
		return

	sisa = format_sisa(hitung_sisa_do(do_no, item_code))

	# do_no dan no_do_2 dipisah: satu DO bisa jadi DO 1 di satu timbangan dan
	# DO 2 di timbangan lain.
	for fieldname, filter_do in (("sisa_do", "do_no"), ("sisa_do_2", "no_do_2")):
		for name in frappe.get_all(
			"Timbangan",
			filters={filter_do: do_no, "kode_barang": item_code, "docstatus": ("!=", 2)},
			pluck="name",
		):
			frappe.db.set_value("Timbangan", name, fieldname, sisa, update_modified=False)


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
	return hitung_sisa_do(do_no, item_code)


@frappe.whitelist()
def get_item_purchase_order_list(purchase_order):
	"""Kode barang yang ada di PO ini.

	Receive "Lain - Lain" tidak membawa SPB maupun DO, jadi PO-nya satu-satunya
	sumber barang untuk timbangan. Dipakai JS untuk mengisi kode_barang sendiri
	kalau PO-nya cuma berisi satu barang.
	"""
	if not purchase_order:
		return []

	rows = frappe.db.sql("""
		select item_code
		from `tabPurchase Order Item`
		where parent = %s
		order by idx
	""", purchase_order, pluck=True)

	# Satu barang bisa muncul di beberapa baris PO (jadwal kirim berbeda); yang
	# dihitung timbangan cuma barangnya, jadi barisnya diringkas tanpa mengubah
	# urutan supaya barang pertama PO tetap yang pertama.
	return list(dict.fromkeys(rows))


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_item_purchase_order(doctype, txt, searchfield, start, page_len, filters):
	"""Daftar barang untuk field kode_barang, dibatasi isi PO yang dipilih."""
	params = {
		"purchase_order": filters.get("purchase_order"),
		"txt": f"%{txt}%",
		"start": start,
		"page_len": page_len,
	}

	return frappe.db.sql("""
		select i.name, i.item_name
		from `tabPurchase Order Item` poi
		join `tabItem` i on i.name = poi.item_code
		where poi.parent = %(purchase_order)s
			and (i.name like %(txt)s or i.item_name like %(txt)s)
		group by i.name
		order by min(poi.idx)
		limit %(start)s, %(page_len)s
	""", params)

@frappe.whitelist()
def baris_po_untuk_timbangan(timbangan):
	"""PO dan baris PO yang dipakai Timbangan ini, untuk mengisi baris Purchase Receipt.

	Yang dipulangkan supplier PO-nya, nama PO-nya, dan satu baris PO yang barangnya
	sama dengan kode_barang timbangan. UOM dan project baris itu wajib dipakai apa
	adanya: ERPNext membandingkan keduanya — beserta item_code — waktu Purchase
	Receipt divalidasi terhadap PO, dan menolak dokumennya kalau berbeda.

	Kalau barangnya muncul di lebih dari satu baris, yang didahulukan baris yang
	belum penuh diterima, supaya penerimaan kedua tidak menempel lagi ke baris
	yang sudah lunas. Kalau tidak ada yang cocok sama sekali, barisnya kosong dan
	yang memanggil boleh tetap menambahkan barangnya tanpa tautan ke PO.
	"""
	kode_barang, purchase_order = frappe.db.get_value(
		"Timbangan", timbangan, ["kode_barang", "purchase_order"]
	)

	if not purchase_order:
		return {}

	po = frappe.get_doc("Purchase Order", purchase_order)
	po.check_permission("read")

	hasil = {"purchase_order": po.name, "supplier": po.supplier}

	cocok = [row for row in po.items if row.item_code == kode_barang]
	if not cocok:
		return hasil

	belum_penuh = [row for row in cocok if flt(row.received_qty) < flt(row.qty)]
	row = (belum_penuh or cocok)[0]

	hasil["baris"] = {
		"name": row.name,
		"item_code": row.item_code,
		"uom": row.uom,
		"conversion_factor": flt(row.conversion_factor),
		"rate": flt(row.rate),
		"warehouse": row.warehouse,
		"project": row.project,
		"qty": flt(row.qty),
		"received_qty": flt(row.received_qty),
		# Spesifikasi, merk, dan country yang dipesan bisa berbeda dari default
		# Item — itulah yang disepakati dengan supplier, jadi yang diterima harus
		# menyebut hal yang sama. row.get supaya site yang tidak memasang custom
		# field-nya tidak ikut pecah.
		"description": row.description,
		"custom_merk": row.get("custom_merk"),
		"custom_country": row.get("custom_country"),
	}

	return hasil

