# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe,math
from frappe.model.document import Document
from frappe.utils import today,flt,getdate,date_diff
from frappe.model.mapper import get_mapped_doc

from sth.mill.utils import get_adjustment_stock, set_rata_rata_rendemen_bulanan


class SoundingStockCPOdiBST(Document):
	def onload(self):
		set_rata_rata_rendemen_bulanan(self)

	def before_validate(self):
		self.gudang = get_warehouse_bst(self.unit)

	def validate(self):
		self.validate_duplicate()
		if not self.gudang:
			frappe.throw(f"Silahkan set default gudang product untuk unit {self.unit}")

		set_rata_rata_rendemen_bulanan(self)
		self.calculate_oer_netto()
		self.calculate_totals()

	def on_submit(self):
		self.create_ste()
		self.update_document_afterwards()
	
	def on_cancel(self):
		self.cancel_ste()
		self.update_document_afterwards()
	
	def on_trash(self):
		self.delete_ste()
		
	def validate_duplicate(self):
		if name := frappe.db.get_value(self.doctype,{"tanggal_proses":self.tanggal_proses,"unit":self.unit,"docstatus":["<",2],"name":["!=",self.name]},"name"):
			frappe.throw(f"Terdapat document dengan tanggal proses yang sama untuk unit {self.unit}: {name}")

	# def validate_backdate(self):
	# 	allowed_diff = frappe.db.get_value("Backdate Setting",{"backdate_doc":self.doctype},"max_days") or 1

	# 	if date_diff(today(),self.tanggal_proses) > allowed_diff:
	# 		frappe.throw(f"Tanggal proses maksimal mundur : {allowed_diff} hari.")

	def validate_previous_documents(self):
		draft_doc = frappe.get_all(
			self.doctype,
			filters=[
				["docstatus","=",0],
				["tanggal_proses","<",self.tanggal_proses]
			],

			pluck="name"
		)

		if draft_doc:
			frappe.throw(f"Terdapat dokument sebelumnya yang belum di submit")

	@frappe.whitelist()
	def get_data(self):
	
		# get_total_stock = frappe.db.sql("""
		# 	select b.actual_qty as qty from `tabBin` b
		# 	join `tabItem` i on b.item_code = i.name
		# 	join `tabWarehouse` w on w.name = b.warehouse
		# 	where i.tipe_barang = "CPO" and w.unit = %s and w.name = %s
		# """,(self.unit,get_warehouse_bst(self.unit)),as_dict=True)
	
		# stock_saat_ini = get_total_stock[0].qty if get_total_stock else 0
		stock_saat_ini = self.get_total_stock()
		self.pengiriman_cpo = self.get_delivery()
		self.stock_awal = flt(stock_saat_ini)
		self.set_adjustment()
		self.tbs_olah = frappe.db.get_value("Data TBS",{"tanggal_produksi":self.tanggal_proses},"tbs_olah") or 0
		self.potongan_sortasi = self.get_sortasi()

		self.calculate_oer_netto()
		self.calculate_totals()

	def get_delivery(self):
		data = frappe.db.sql("""
			select sum(coalesce(netto_2,0)) as qty
			from `tabTimbangan` t
			join `tabItem` i on t.kode_barang = i.name
			where i.tipe_barang = "CPO" and t.docstatus = 1 and unit  = %s and t.posting_date = %s
		""",(self.unit,self.tanggal_proses),as_dict=True)

		return data[0].qty if data else 0

	def get_sortasi(self):
		data_sortasi = frappe.db.sql("""
			select sum(coalesce(netto - netto_2,0)) as qty
			from `tabTimbangan` t
			join `tabItem` i on t.kode_barang = i.name
			where i.tipe_barang = 'TBS' and t.docstatus = 1 and unit  = %s and t.posting_date = %s
		""",(self.unit,self.tanggal_proses),as_dict=True)

		return data_sortasi[0].qty if data_sortasi else 0

	def get_total_stock(self):
		warehouse = get_warehouse_bst(self.unit)
		item_code = frappe.db.get_value("Item",{"tipe_barang": "CPO"})

		if not (warehouse and item_code):
			return 0

		terakhir = frappe.db.sql("""
			select qty_after_transaction
			from `tabStock Ledger Entry`
			where item_code = %s and warehouse = %s and is_cancelled = 0
				and posting_date < %s
			order by posting_date desc, posting_time desc, creation desc
			limit 1
		""",(item_code, warehouse, self.tanggal_proses))

		return flt(terakhir[0][0]) if terakhir else 0

	def set_adjustment(self):
		"""Pecah stock awal jadi bagian sebelum koreksi dan koreksinya sendiri.

		Sekadar keterangan: produksi dan OER tetap dihitung dari stock_awal yang
		utuh, yaitu yang sudah termasuk adjustment. Stock awal di sini saldo
		berjalan ditambah pengiriman hari itu, jadi koreksi yang diposting di
		tanggal prosesnya sendiri sudah ikut di dalamnya.
		"""
		self.adjustment = get_adjustment_stock(
			frappe.db.get_value("Item", {"tipe_barang": "CPO"}),
			get_warehouse_bst(self.unit),
			self.unit,
			self.doctype,
			self.tanggal_proses,
			termasuk_tanggal_proses=True,
		)
		self.stock_awal_sebelum_adjustment = flt(self.stock_awal) - flt(self.adjustment)

	def calculate_totals(self) :
		total_stock = self.tonase_sebenarnya + self.tonase_sebenarnya_2
		total_produksi = (flt(total_stock) + flt(self.pengiriman_cpo)) - flt(self.stock_awal)
		self.stock_bst = total_stock
		self.produksi_cpo = total_produksi
	
	def calculate_oer_netto(self):
		self.oer_netto_1 = 0
		self.oer_netto_2 = 0

		if self.tbs_olah > 0 :
			self.oer_netto_1 = (self.produksi_cpo / self.tbs_olah * 100) 
			self.oer_netto_2 = (self.produksi_cpo / (self.tbs_olah - self.potongan_sortasi) * 100)


	def create_ste(self):
		if round(self.produksi_cpo,2) == 0: return

		ste_type = "Material Receipt" if self.produksi_cpo > 0 else "Material Issue"
		def postprocess(source,target):
			 
			target.stock_entry_type = ste_type

			# Tanpa ini validate_posting_time menimpa posting_date dengan hari
			# ini, jadi penerimaan bertanggal mundur tercatat di tanggal STE-nya
			# dibuat, bukan di tanggal soundingnya.
			target.set_posting_time = 1
			target.posting_time = "23:59:59"

			update_fields = (
				"item_name",
				"stock_uom",
				"description",
				"expense_account",
				"cost_center",
				"conversion_factor",
				"barcode",
				"uom"
			)

			# akun_expense = ""
			# procurement_settings = frappe.get_single("Procurement Settings")
			
			# for row in procurement_settings.akun_pengeluaran_table:
			# 	if row.company == self.company:
			# 		akun_expense = row.akun_pengeluaran

			item = target.append("items")
			item.item_code = frappe.db.get_value("Item",{"tipe_barang": "CPO"})
			item.qty = abs(self.produksi_cpo)

			if ste_type == "Material Receipt":
				item.t_warehouse = self.gudang
			else:
				item.s_warehouse = self.gudang

			item_details = target.get_item_details(
				frappe._dict(
					{
						"item_code": item.item_code,
						"company": target.company,
						"project": target.project,
					}
				),
				for_update=True,
			)

			for field in update_fields:
				if not item.get(field):
					item.set(field, item_details.get(field))
				if field == "conversion_factor" and item.uom == item_details.get("stock_uom"):
					item.set(field, item_details.get(field))
			
			
			target.run_method("set_missing_values")
			

		mapper = {
			"Sounding Stock CPO di BST": {
				"doctype": "Stock Entry",
				"field_map": {
					"name":"references",
					"doctype": "reference_doctype",
					"tanggal_proses":"posting_date",
					
				}
			},
		}

		# posting_date diambil dari tanggal_proses, bukan field tanggal: tanggal
		# adalah kapan soundingnya dicatat, sementara produksinya milik hari
		# prosesnya — sama seperti tbs olah dan potongan sortasi yang diambil per
		# tanggal_proses di get_data(). Sama dengan Sounding Palm Kernel.
		doc = get_mapped_doc(self.doctype,self.name,mapper,None,postprocess,True)
		doc.insert()
		doc.submit()
	
	def cancel_ste(self):
		ste = frappe.db.get_all("Stock Entry",{"references": self.name})
		for row in ste:
			doc = frappe.get_doc("Stock Entry",row)
			doc.cancel()
	
	def delete_ste(self):
		ste = frappe.db.get_all("Stock Entry",{"references": self.name})
		for row in ste:
			doc = frappe.get_doc("Stock Entry",row)
			doc.delete()

	def recreate_ste(self):
		self.cancel_ste()
		self.delete_ste()
		self.create_ste()


	def update_document_afterwards(self):
		docs = frappe.get_all(
			"Sounding Stock CPO di BST",
			filters=[
				["tanggal_proses",">",self.tanggal_proses],
				["docstatus","!=",2],
			],
			pluck="name",
			order_by="tanggal_proses"
		)

		for name in docs:
			doc = frappe.get_doc(self.doctype,name)
			doc.get_data()
			doc.recreate_ste()

			doc.db_update_all()




@frappe.whitelist()
def get_ukuran_sounding(tinggi,bst,pabrik):
	
	desimal, bulat = math.modf(flt(tinggi))

	ukuran_sounding = frappe.db.sql("""
		select usbd.volume from `tabUkuran Sounding BST` usb
		join `tabUkuran Sounding BST Detail` usbd on usbd.parent = usb.name
		where usb.nama_bst = %s and usbd.tinggi = %s and usb.pabrik = %s
	""",(bst,bulat,pabrik),as_dict=True)
	volume_sounding = ukuran_sounding[0].volume if ukuran_sounding else 0
	desimal = round(desimal * 10,1) 
	if desimal > 0:
		ukuran_cincin = frappe.db.sql("""
			select ucbd.liter from `tabUkuran Cincin BST` ucb
			join `tabUkuran Cincin BST Detail` ucbd on ucbd.parent = ucb.name
			where ucb.sampai_ukuran >= %s and %s >= ucb.dari_ukuran and ucb.nama_bst = %s and ucbd.mm = %s and ucb.pabrik = %s
		""",(bulat,bulat,bst,desimal,pabrik),as_dict=True)
		print(ukuran_cincin)
		volume_sounding += ukuran_cincin[0].liter if ukuran_cincin else 0

	return volume_sounding

@frappe.whitelist()
def get_warehouse_bst(unit):
	return frappe.db.get_value("Warehouse",{"unit":unit,"warehouse_category": "Product CPO"})

@frappe.whitelist()
def get_berat_jenis(pabrik,suhu):
	return frappe.get_value("Ukuran Berat Jenis Detail",{"pabrik": pabrik,"parent": suhu},["berat_jenis"])