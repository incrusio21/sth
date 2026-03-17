# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today,flt

class SoundingStockCPOdiBST(Document):
	@frappe.whitelist()
	def get_data(self):
		get_delivery = frappe.db.sql("""
			select coalesce(sum(dni.stock_qty),0) as qty from `tabDelivery Note` dn
			join `tabDelivery Note Item` dni on dni.parent = dn.name
			join `tabItem` i on dni.item_code = i.name
			where dn.posting_date = %s and i.item_cpo = 1
		""",(today()),as_dict=True)

		get_total_stock = frappe.db.sql("""
			select coalesce(sum(actual_qty),0) as qty from `tabBin` b
			join `tabItem` i on b.item_code = i.name
			where i.item_cpo = 1
		""",as_dict=True)

		get_sortasi = frappe.db.sql("""
			select coalesce(sum(t.netto - t.netto_2),0) as sortasi
			from `tabTimbangan` t
			where t.posting_date = %s and t.docstatus = 1
		""",(today()),as_dict=True)

		self.pengiriman_cpo = get_delivery[0].qty if get_delivery else 0
		self.stock_bst = get_total_stock[0].qty if get_total_stock else 0
		self.stock_awal = flt(self.stock_bst) + flt(self.pengiriman_cpo)
		self.tbs_olah = frappe.db.get_value("Data TBS",{"tanggal":today()},"tbs_olah") or 0
		self.potongan_sortasi = get_sortasi[0].sortasi if get_sortasi else 0

@frappe.whitelist()
def get_ukuran_sounding(tinggi,bst):
	res = frappe.db.sql("""
		select usbd.volume from `tabUkuran Sounding BST` usb
		join `tabUkuran Sounding BST Detail` usbd on usbd.parent = usb.name
		where usb.name = %s and usbd.tinggi = %s
	""",(bst,tinggi),as_dict=True)

	return res[0].volume if res else 0