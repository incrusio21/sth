# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt

class PenginputanStockByProduct(Document):
	@frappe.whitelist()
	def get_stock(self):
		get_delivery = frappe.db.sql("""
			select coalesce(sum(dni.stock_qty),0) as qty from `tabDelivery Note` dn
			join `tabDelivery Note Item` dni on dni.parent = dn.name
			join `tabItem` i on dni.item_code = i.name
			where dn.posting_date = %s and dni.item_code = %s and dn.unit = %s
		""",(self.tanggal_produksi,self.nama_barang,self.unit),as_dict=True)

		get_total_stock = frappe.db.sql("""
			select coalesce(sum(netto_2),0) as qty from `tabTimbangan` b
			join `tabItem` i on b.kode_barang = i.name
			where i.name = %s and b.unit = %s
		""",(self.nama_barang,self.unit),as_dict=True)

		self.pengiriman = get_delivery[0].qty if get_delivery else 0
		stock_saat_ini = get_total_stock[0].qty if get_total_stock else 0
		self.stock_awal = flt(stock_saat_ini) + flt(self.pengiriman)

		tbs_olah = frappe.db.get_value("Data TBS",{"tanggal_produksi": self.tanggal_produksi},["tbs_olah"])
		fields = []
		if self.tipe == "Cangkang":
			pass
		elif self.tipe == "Fiber Bunch Press":
			pass
		elif self.tipe == "Empty Bunch":
			pass
		elif self.tipe == "Solid":
			pass

		if not fields: return
		data_mass_balance = frappe.get_all("Mass Balance",fields=fields,order_by="date desc, jam desc",limit=1)
		result = 1
		for index,field in enumerate(fields):
			result *= flt(data_mass_balance[index][field])
		
		self.produksi = result * flt(tbs_olah)