# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe,math
from frappe.model.document import Document
from frappe.utils import today,flt,getdate
from frappe.model.mapper import get_mapped_doc

from sth.mill.utils import get_adjustment_stock, set_rata_rata_rendemen_bulanan


class SoundingStockCPOdiBST(Document):
	def onload(self):
		set_rata_rata_rendemen_bulanan(self)

	def before_validate(self):
		self.gudang = get_warehouse_bst(self.unit)

	def validate(self):
		if not self.gudang:
			frappe.throw(f"Silahkan set default gudang product untuk unit {self.unit}")

		set_rata_rata_rendemen_bulanan(self)

	def on_submit(self):
		if self.produksi_cpo > 0:
			self.create_ste()
	
	def on_cancel(self):
		ste = frappe.db.get_all("Stock Entry",{"references": self.name})
		for row in ste:
			doc = frappe.get_doc("Stock Entry",row)
			doc.cancel()
	
	def on_trash(self):
		ste = frappe.db.get_all("Stock Entry",{"references": self.name})
		for row in ste:
			doc = frappe.get_doc("Stock Entry",row)
			doc.delete()
		

	@frappe.whitelist()
	def get_data(self):
		get_delivery = frappe.db.sql("""
			select sum(coalesce(netto_2,0)) as qty
			from `tabTimbangan` t
			join `tabItem` i on t.kode_barang = i.name
			where i.tipe_barang = "CPO" and t.docstatus = 1 and unit  = %s and t.posting_date = %s
		""",(self.unit,self.tanggal_proses),as_dict=True)

		get_total_stock = frappe.db.sql("""
			select b.actual_qty as qty from `tabBin` b
			join `tabItem` i on b.item_code = i.name
			join `tabWarehouse` w on w.name = b.warehouse
			where i.tipe_barang = "CPO" and w.unit = %s and w.name = %s
		""",(self.unit,get_warehouse_bst(self.unit)),as_dict=True)

		data_sortasi = frappe.db.sql("""
			select sum(coalesce(netto - netto_2,0)) as qty
			from `tabTimbangan` t
			join `tabItem` i on t.kode_barang = i.name
			where i.tipe_barang = 'TBS' and t.docstatus = 1 and unit  = %s and t.posting_date = %s
		""",(self.unit,self.tanggal_proses),as_dict=True)
		
		stock_saat_ini = get_total_stock[0].qty if get_total_stock else 0
		self.pengiriman_cpo = get_delivery[0].qty if get_delivery else 0
		self.stock_awal = flt(stock_saat_ini) + flt(self.pengiriman_cpo)
		self.set_adjustment()
		self.tbs_olah = frappe.db.get_value("Data TBS",{"tanggal_produksi":self.tanggal_proses},"tbs_olah") or 0
		self.potongan_sortasi = data_sortasi[0].qty if data_sortasi else 0

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

	def create_ste(self):
		ste_type = "Material Receipt" if self.produksi_cpo > 0 else "Material Issue"
		def postprocess(source,target):
			target.stock_entry_type = ste_type

			# Tanpa ini validate_posting_time menimpa posting_date dengan hari
			# ini, jadi penerimaan bertanggal mundur tercatat di tanggal STE-nya
			# dibuat, bukan di tanggal soundingnya.
			target.set_posting_time = 1
			
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
					"jam":"posting_time"
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