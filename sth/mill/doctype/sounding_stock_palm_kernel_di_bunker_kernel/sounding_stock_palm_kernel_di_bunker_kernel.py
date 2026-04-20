# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate,flt
from frappe.model.mapper import get_mapped_doc

class SoundingStockPalmKerneldiBunkerKernel(Document):
	def before_save(self):
		self.hasil_titik_sounding = []
		self.rekap_hasil = []

		if self.ukuran_detail:
			self.calculate_hasil_titik_sounding()
			self.add_rekap_hasil()
		
		self.calculate_volume_sounding()
		self.produksi = self.volume_sounding - self.stock_akhir 
		self.ker_netto_1 = self.produksi / self.tbs_olah*100 if self.tbs_olah else 0 
		self.ker_netto_2 = self.produksi/(self.tbs_olah - self.sortasi)*100 if self.tbs_olah else 0

	def on_submit(self):
		if self.produksi > 0:
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

	def calculate_hasil_titik_sounding(self):
		result = frappe._dict()
		for data in self.ukuran_detail:
			result.setdefault(data.nama_kompartemen_bunker, []).append(data.hasil_titik_sounding)

		if self.jumlah_hasil_sounding == "2 rata - rata":
			for key,value in result.items():
				avg_left,avg_right = self.split_and_avg(value)
				self.append("hasil_titik_sounding",{
					"nama_kompartemen_bunker": key,
					"rata_rata_hasil": avg_left,
					"hasil_pembulatan": round(avg_left),
					"total_hitungan": self.tinggi_normal_bunker - round(avg_left) if self.tinggi_normal_bunker > 0 else round(avg_left)
				})

				self.append("hasil_titik_sounding",{
					"nama_kompartemen_bunker": key,
					"rata_rata_hasil": avg_right,
					"hasil_pembulatan": round(avg_right),
					"total_hitungan": self.tinggi_normal_bunker - round(avg_right) if self.tinggi_normal_bunker > 0 else round(avg_right)
				})
		else :
			for key,value in result.items():
				value = list(map(int, value))
				avg = sum(value) / len(value)

				self.append("hasil_titik_sounding",{
					"nama_kompartemen_bunker": key,
					"rata_rata_hasil": avg,
					"hasil_pembulatan": round(avg),
					"total_hitungan": self.tinggi_normal_bunker - round(avg) if self.tinggi_normal_bunker > 0 else round(avg)
				})

	def add_rekap_hasil(self):
		for row in self.hasil_titik_sounding:
			parent_doc = frappe.db.get_value("Ukuran Bunker Kernel Silo",{"pabrik":self.pabrik,"kompartemen_bunker":row.nama_kompartemen_bunker}) or frappe.db.get_value("Ukuran Bunker Kernel Silo",{"pabrik":self.pabrik,"default":1})

			tonase,liter = frappe.get_value("Ukuran Bunker Kernel Silo Detail",{"parent": parent_doc,"ukuran":row.total_hitungan, },["tonase","liter"]) or (0,0)

			volume = tonase * 1000 if flt(tonase) > 0 else liter

			self.append("rekap_hasil",{
				"kompartemen": row.nama_kompartemen_bunker,
				"ukuran": row.total_hitungan,
				"volume": volume,
				"netto" : volume * self.berat_jenis if self.berat_jenis > 0 else volume
			})

	def calculate_volume_sounding(self):
		netto = 0
		
		for row in self.rekap_hasil:
			netto += row.netto

		self.volume_sounding = netto

	@frappe.whitelist()
	def get_stock(self):
		get_delivery = frappe.db.sql("""
			select sum(coalesce(netto_2,0)) as qty
			from `tabTimbangan` t
			join `tabItem` i on t.kode_barang = i.name
			where i.tipe_barang = 'Palm Kernel' and t.docstatus = 1 and unit  = %s and t.posting_date = %s
		""",(self.unit,self.tanggal_proses),as_dict=True)

		get_total_stock = frappe.db.sql("""
			select b.actual_qty as qty from `tabBin` b
			join `tabItem` i on b.item_code = i.name
			join `tabWarehouse` w on w.name = b.warehouse
			where i.tipe_barang = 'Palm Kernel' and w.unit = %s and w.name = %s
		""",(self.unit,get_warehouse_palm(self.unit)),as_dict=True)

		data_sortasi = frappe.db.sql("""
			select sum(coalesce(netto - netto_2,0)) as qty
			from `tabTimbangan` t
			join `tabItem` i on t.kode_barang = i.name
			where i.tipe_barang = 'TBS' and t.docstatus = 1 and unit  = %s and t.posting_date = %s
		""",(self.unit,self.tanggal_proses),as_dict=True)


		self.stock_akhir = get_total_stock[0].qty if get_total_stock else 0
		self.pengiriman = get_delivery[0].qty if get_delivery else 0
		self.stock_awal = flt(self.stock_akhir) - flt(self.pengiriman_palm)
		self.tbs_olah = frappe.db.get_value("Data TBS",{"tanggal_produksi":self.tanggal_proses},"tbs_olah") or 0
		self.sortasi = data_sortasi[0].qty if data_sortasi else 0

	def split_and_avg(self,arr):
		arr = list(map(int, arr))
		mid = len(arr) // 2
		
		left = arr[:mid + (len(arr) % 2)]
		right = arr[mid:]
		
		return sum(left)/len(left), sum(right)/len(right)
	
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
			item.item_code = frappe.db.get_value("Item",{"tipe_barang": "Palm Kernel"})
			item.qty = self.produksi
			item.t_warehouse = frappe.db.get_value("Warehouse",{"unit": self.unit,"warehouse_category": "Product Palm Kernel"})

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
			"Sounding Stock Palm Kernel di Bunker Kernel": {
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


def get_warehouse_palm(unit):
	return frappe.db.get_value("Warehouse",{"unit":unit,"warehouse_category": "Product Palm Kernel"})

@frappe.whitelist()
def get_berat_limas(density,kompartemen,pabrik):
	query = frappe.db.sql("""
		select bjld.berat from `tabUkuran Berat Jenis Limas` bjl
		join `tabUkuran Berat Jenis Limas Detail` bjld on bjl.name = bjld.parent
		where bjl.pabrik = %s and bjl.kompartemen = %s and bjld.density = %s 
	""",(pabrik,kompartemen,density),as_dict=True)

	return query[0].berat if query else 0 