# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today,flt,getdate
from frappe.model.mapper import get_mapped_doc

class SoundingStockCPOdiBST(Document):
	@frappe.whitelist()
	def get_data(self):
		get_stock_data = frappe.db.sql("""
			select coalesce(netto_2,0) as qty ,posting_date
			from `tabTimbangan` t
			join `tabItem` i on t.kode_barang = i.name
			where i.item_cpo = 1 and t.docstatus = 1 and unit  = %s
		""",(self.unit),as_dict=True)

		data_sortasi = frappe.db.sql("""
			select sum(coalesce(netto - netto_2,0)) as qty
			from `tabTimbangan` t
			join `tabItem` i on t.kode_barang = i.name
			where i.item_tbs = 1 and t.docstatus = 1 and unit  = %s and t.posting_date = %s
		""",(self.unit,self.tanggal_proses),as_dict=True)

		pengiriman_cpo = stock_bst = 0
		for data in get_stock_data:
			if getdate(data.posting_date) == getdate(self.tanggal_proses):
				pengiriman_cpo += data.qty
			
			stock_bst += data.qty
		self.stock_bst = 0
		self.pengiriman_cpo = pengiriman_cpo
		self.stock_awal = flt(stock_bst) + flt(self.pengiriman_cpo)
		self.tbs_olah = frappe.db.get_value("Data TBS",{"tanggal_produksi":self.tanggal_proses},"tbs_olah") or 0
		self.potongan_sortasi = data_sortasi[0].qty if data_sortasi else 0

	def create_ste(self,qty,gudang):
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

			akun_expense = ""
			procurement_settings = frappe.get_single("Procurement Settings")
			
			for row in procurement_settings.akun_pengeluaran_table:
				if row.company == self.company:
					akun_expense = row.akun_pengeluaran

			item = target.append("items")
			item.item_code = "CPO"
			item.qty = qty
			item.t_warehouse = gudang

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
def get_warehouse_bst(pabrik):
	return frappe.get_all("Master BST Detail",{"parent": ["in",["BST 01","BST 02"]],"pabrik":pabrik},["gudang","parent as name"])

@frappe.whitelist()
def get_berat_jenis(pabrik,suhu):
	return frappe.get_value("Ukuran Berat Jenis Detail",{"pabrik": pabrik,"parent": suhu},["berat_jenis"])