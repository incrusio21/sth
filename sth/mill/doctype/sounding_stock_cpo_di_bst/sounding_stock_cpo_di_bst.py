# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today,flt,getdate
from frappe.model.mapper import get_mapped_doc

class SoundingStockCPOdiBST(Document):
	def before_validate(self):
		self.gudang = get_warehouse_bst(self.unit)

	def validate(self):
		if not self.gudang:
			frappe.throw(f"Silahkan set default gudang product untuk unit {self.unit}")

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
		self.tbs_olah = frappe.db.get_value("Data TBS",{"tanggal_produksi":self.tanggal_proses},"tbs_olah") or 0
		self.potongan_sortasi = data_sortasi[0].qty if data_sortasi else 0

	def create_ste(self):
		def postprocess(source,target):
			target.stock_entry_type = "Material Receipt"
			
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
			item.qty = self.produksi_cpo
			item.t_warehouse = self.gudang

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
					"tanggal":"posting_date"
				}
			},
		}

		doc = get_mapped_doc(self.doctype,self.name,mapper,None,postprocess,True)
		doc.insert()
		doc.submit()

@frappe.whitelist()
def get_ukuran_sounding(tinggi,bst,pabrik):
	res = frappe.db.sql("""
		select usbd.volume from `tabUkuran Sounding BST` usb
		join `tabUkuran Sounding BST Detail` usbd on usbd.parent = usb.name
		where usb.name = %s and usbd.tinggi = %s and usb.pabrik = %s
	""",(bst,tinggi,pabrik),as_dict=True)

	return res[0].volume if res else 0

@frappe.whitelist()
def get_warehouse_bst(unit):
	return frappe.db.get_value("Warehouse",{"unit":unit,"warehouse_category": "Product CPO"})

@frappe.whitelist()
def get_berat_jenis(pabrik,suhu):
	return frappe.get_value("Ukuran Berat Jenis Detail",{"pabrik": pabrik,"parent": suhu},["berat_jenis"])