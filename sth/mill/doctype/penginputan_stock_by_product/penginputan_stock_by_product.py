# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt
from frappe.model.mapper import get_mapped_doc

class PenginputanStockByProduct(Document):
	def on_submit(self):
		if flt(self.input_dipakai_pabrik) > 0:
			self.create_ste("Out")
		
		if flt(self.produksi) > 0:
			self.create_ste("In")

	@frappe.whitelist()
	def get_stock(self):
		get_delivery = frappe.db.sql("""
			select coalesce(sum(dni.stock_qty),0) as qty from `tabDelivery Note` dn
			join `tabDelivery Note Item` dni on dni.parent = dn.name
			join `tabItem` i on dni.item_code = i.name
			where dn.posting_date = %s and dni.item_code = %s and dn.unit = %s
		""",(self.tanggal_proses,self.nama_barang,self.unit),as_dict=True)

		get_total_stock = frappe.db.sql("""
			select coalesce(sum(netto_2),0) as qty from `tabTimbangan` b
			join `tabItem` i on b.kode_barang = i.name
			where i.name = %s and b.unit = %s
		""",(self.nama_barang,self.unit),as_dict=True)

		self.pengiriman = get_delivery[0].qty if get_delivery else 0
		stock_saat_ini = get_total_stock[0].qty if get_total_stock else 0
		self.stock_awal = flt(stock_saat_ini) + flt(self.pengiriman)

		self.data_olah_tbs = frappe.db.get_value("Data TBS",{"tanggal_produksi": self.tanggal_proses},["tbs_olah"])
		
		fields = []
		if self.tipe == "Cangkang":
			fields = ["ltds_1nut","ltds_2nut","wet_shellnut"]
		elif self.tipe == "Fiber Bunch Press":
			fields = ["fiber_bunch_presstbs"]
		elif self.tipe == "Empty Bunch":
			fields = ["empty_bunchtbs"]
		elif self.tipe == "Solid":
			fields = ["solid_decantertbs"]

		if not fields: return
		data_mass_balance = frappe.get_all("Mass Balance",fields=fields,order_by="date desc, jam desc",limit=1)
		result = 0
		for field in fields:
			result += flt(data_mass_balance[0][field])
		
		self.produksi = result * flt(self.data_olah_tbs)
	
	def create_ste(self,type):
		def postprocess(source,target):
			target.stock_entry_type = "Material Issue" if type == "Out" else "Material Receipt"
			
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

			akun_expense = ""
			procurement_settings = frappe.get_single("Procurement Settings")
			
			for row in procurement_settings.akun_pengeluaran_table:
				if row.company == self.company:
					akun_expense = row.akun_pengeluaran

			item = target.append("items")
			item.item_code = source.nama_barang
			item.qty = source.input_dipakai_pabrik if type == "Out" else source.produksi
			if type == "Out":
				item.s_warehouse = source.gudang
			else:
				item.t_warehouse = source.gudang
		

			item_details = target.get_item_details(
				frappe._dict(
					{
						"item_code": item.item_code,
						"company": target.company,
						"project": target.project,
						"expense_account": akun_expense,
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
			"Penginputan Stock By Product": {
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
		
		# self.ste_reference = doc.name