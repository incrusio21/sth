# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate,flt

class SoundingStockPalmKerneldiBunkerKernel(Document):
	def before_save(self):
		self.hasil_titik_sounding = []
		self.rekap_hasil = []

		if self.ukuran_detail:
			self.calculate_hasil_titik_sounding()
			self.add_rekap_hasil()
		
		self.calculate_volume_sounding()
		self.produksi = self.volume_sounding - self.stock_akhir 
		self.ker_netto_1 = self.produksi/self.tbs_olah*100
		self.ker_netto_2 = self.produksi/(self.tbs_olah - self.sortasi)*100

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
					"total_hitungan": self.tinggi_normal_bunker - round(avg_left)
				})

				self.append("hasil_titik_sounding",{
					"nama_kompartemen_bunker": key,
					"rata_rata_hasil": avg_right,
					"hasil_pembulatan": round(avg_right),
					"total_hitungan": self.tinggi_normal_bunker - round(avg_right)
				})
		else :
			for key,value in result.items():
				value = list(map(int, value))
				avg = sum(value) / len(value)

				self.append("hasil_titik_sounding",{
					"nama_kompartemen_bunker": key,
					"rata_rata_hasil": avg,
					"hasil_pembulatan": round(avg),
					"total_hitungan": self.tinggi_normal_bunker - round(avg)
				})

	def add_rekap_hasil(self):
		for row in self.hasil_titik_sounding:
			parent_doc = frappe.db.get_value("Ukuran Bunker Kernel Silo",{"pabrik":self.pabrik,"kompartemen_bunker":row.nama_kompartemen_bunker}) or frappe.db.get_value("Ukuran Bunker Kernel Silo",{"pabrik":self.pabrik,"default":1})
			
			volume = 0
			tonase,liter = frappe.get_value("Ukuran Bunker Kernel Silo Detail",{"parent": parent_doc,"ukuran":row.total_hitungan, },["tonase","liter"])

			if flt(tonase) > 0:
				volume = (volume + tonase) * 1000
			else:
				volume += liter

			self.append("rekap_hasil",{
				"ukuran": row.total_hitungan,
				"volume": volume,
				"netto" : volume * self.berat_jenis if self.berat_jenis > 0 else volume
			})

	def calculate_volume_sounding(self):
		volume = 0
		
		for row in self.rekap_hasil:
			volume += row.volume

		self.volume_sounding = volume

	@frappe.whitelist()
	def get_stock(self):
		get_stock_data = frappe.db.sql("""
			select coalesce(netto_2,0) as qty,posting_date
			from `tabTimbangan` t
			join `tabItem` i on t.kode_barang = i.name
			where i.item_palm_kernel = 1 and t.docstatus = 1 and unit  = %s
		""",(self.unit),as_dict=True)

		data_sortasi = frappe.db.sql("""
			select sum(coalesce(netto - netto_2,0)) as qty
			from `tabTimbangan` t
			join `tabItem` i on t.kode_barang = i.name
			where i.item_tbs = 1 and t.docstatus = 1 and unit  = %s and t.posting_date = %s
		""",(self.unit,self.tanggal_proses),as_dict=True)

		pengiriman_palm = stock_akhir = 0
		for data in get_stock_data:
			if getdate(data.posting_date) == getdate(self.tanggal_proses):
				x += data.qty
			
			stock_akhir += data.qty

		self.stock_akhir = stock_akhir
		self.pengiriman = pengiriman_palm
		self.stock_awal = flt(stock_akhir) - flt(pengiriman_palm)
		self.tbs_olah = frappe.db.get_value("Data TBS",{"tanggal_produksi":self.tanggal_proses},"tbs_olah") or 0
		self.sortasi = data_sortasi[0].qty if data_sortasi else 0

	def split_and_avg(self,arr):
		arr = list(map(int, arr))
		mid = len(arr) // 2
		
		left = arr[:mid + (len(arr) % 2)]
		right = arr[mid:]
		
		return sum(left)/len(left), sum(right)/len(right)
