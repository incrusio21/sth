# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today,flt,getdate

class SoundingStockCPOdiBST(Document):
	@frappe.whitelist()
	def get_data(self):
		get_stock_data = frappe.db.sql("""
			select coalesce(netto_2,0) as qty, coalesce(netto - netto_2,0) as sortasi ,posting_date
			from `tabTimbangan` t
			join `tabItem` i on t.kode_barang = i.name
			where i.item_cpo = 1 and t.docstatus = 1 and unit  = %s
		""",(self.unit),as_dict=True)

		pengiriman_cpo = stock_bst = sortasi = 0
		for data in get_stock_data:
			if getdate(data.posting_date) == getdate(self.tanggal_proses):
				pengiriman_cpo += data.qty
				sortasi += data.sortasi
			
			stock_bst += data.qty

		self.pengiriman_cpo = pengiriman_cpo
		self.stock_bst = stock_bst
		self.stock_awal = flt(self.stock_bst) + flt(self.pengiriman_cpo)
		self.tbs_olah = frappe.db.get_value("Data TBS",{"tanggal_produksi":self.tanggal_proses},"tbs_olah") or 0
		self.potongan_sortasi = sortasi

@frappe.whitelist()
def get_ukuran_sounding(tinggi,bst,pabrik):
	res = frappe.db.sql("""
		select usbd.volume from `tabUkuran Sounding BST` usb
		join `tabUkuran Sounding BST Detail` usbd on usbd.parent = usb.name
		where usb.name = %s and usbd.tinggi = %s and usb.pabrik = %s
	""",(bst,tinggi,pabrik),as_dict=True)

	return res[0].volume if res else 0

@frappe.whitelist()
def get_warehouse_bst(pabrik):
	return frappe.get_all("Master BST Detail",{"parent": ["in",["BST 01","BST 02"]],"pabrik":pabrik},["gudang","parent as name"])

@frappe.whitelist()
def get_berat_jenis(pabrik,suhu):
	return frappe.get_value("Ukuran Berat Jenis Detail",{"pabrik": pabrik,"parent": suhu},["berat_jenis"])