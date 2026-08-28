# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate,flt,now
from frappe.model.mapper import get_mapped_doc

class SoundingStockPalmKerneldiBunkerKernel(Document):
	def before_save(self):
		self.hasil_titik_sounding = []
		self.rekap_hasil = []

		if self.ukuran_detail:
			self.calculate_hasil_titik_sounding()
			self.add_rekap_hasil()
		
		self.calculate_volume_sounding()
		# self.produksi = self.volume_sounding - self.stock_akhir 
		# self.ker_netto_1 = self.produksi / self.tbs_olah*100 if self.tbs_olah else 0 
		# self.ker_netto_2 = self.produksi/(self.tbs_olah - self.sortasi)*100 if self.tbs_olah else 0

	def validate(self):
		self.hitung_produksi()

	def hitung_produksi(self):
		self.stock_akhir = self.volume_sounding
		self.produksi = flt(self.stock_akhir) - flt(self.stock_awal) + flt(self.pengiriman)

		tbs_olah_bersih = flt(self.tbs_olah) - flt(self.sortasi)
		self.ker_netto_1 = self.produksi / self.tbs_olah*100 if self.tbs_olah else 0 
		self.ker_netto_2 = self.produksi / tbs_olah_bersih*100 if tbs_olah_bersih else 0

	def on_submit(self):
		if self.produksi:
			self.create_ste()
	
	def on_cancel(self):
		ste = frappe.db.get_all("Stock Entry",{"references": self.name})
		for row in ste:
			doc = frappe.get_doc("Stock Entry",row)
			if doc.docstatus == 1:
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

		self.volume_sounding = round(netto,-1)

	@frappe.whitelist()
	def get_stock(self):
		get_delivery = frappe.db.sql("""
			select sum(coalesce(netto_2,0)) as qty
			from `tabTimbangan` t
			join `tabItem` i on t.kode_barang = i.name
			where i.tipe_barang = 'Palm Kernel' and t.docstatus = 1 and unit  = %s and t.posting_date = %s
		""",(self.unit,self.tanggal_proses),as_dict=True)

		data_sortasi = frappe.db.sql("""
			select sum(coalesce(netto - netto_2,0)) as qty
			from `tabTimbangan` t
			join `tabItem` i on t.kode_barang = i.name
			where i.tipe_barang = 'TBS' and t.docstatus = 1 and unit  = %s and t.posting_date = %s
		""",(self.unit,self.tanggal_proses),as_dict=True)

		self.stock_awal = get_stock_awal(self.unit, self.tanggal_proses, self.creation)

		self.pengiriman = get_delivery[0].qty if get_delivery else 0
		self.tbs_olah = frappe.db.get_value("Data TBS",{"tanggal_produksi":self.tanggal_proses},"tbs_olah") or 0
		self.sortasi = data_sortasi[0].qty if data_sortasi else 0

	def split_and_avg(self,arr):
		arr = list(map(int, arr))
		mid = len(arr) // 2
		
		left = arr[:mid + (len(arr) % 2)]
		right = arr[mid:]
		
		return sum(left)/len(left), sum(right)/len(right)
	
	def create_ste(self):
		ste_type = "Material Receipt" if self.produksi > 0 else "Material Issue"

		def postprocess(source,target):
			target.stock_entry_type = ste_type
			
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
			item.qty = abs(self.produksi)

			if ste_type == "Material Receipt":
				item.t_warehouse = get_warehouse_palm(self.unit)
			else:
				item.s_warehouse = get_warehouse_palm(self.unit)

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


def get_stock_awal(unit, tanggal_proses, creation=None):
	"""Stock awal = stock akhir sounding sebelumnya di unit yang sama.

	Bukan saldo Stock Ledger: saldo gudang di akhir tanggal proses sudah
	dipotong pengiriman hari itu, sedangkan stock awal yang dimaksud adalah
	isi bunker sebelum produksi hari itu masuk. Sounding yang dibatalkan
	dilewati supaya rantainya tidak putus.
	"""
	if not (unit and tanggal_proses):
		return 0

	sebelumnya = frappe.db.sql("""
		select stock_akhir
		from `tabSounding Stock Palm Kernel di Bunker Kernel`
		where unit = %(unit)s and docstatus < 2
			and (
				tanggal_proses < %(tanggal_proses)s
				or (tanggal_proses = %(tanggal_proses)s and creation < %(creation)s)
			)
		order by tanggal_proses desc, creation desc
		limit 1
	""", {
		"unit": unit,
		"tanggal_proses": tanggal_proses,
		"creation": creation or now(),
	})

	return flt(sebelumnya[0][0]) if sebelumnya else 0

@frappe.whitelist()
def get_berat_limas(density,kompartemen,pabrik):
	query = frappe.db.sql("""
		select bjld.berat from `tabUkuran Berat Jenis Limas` bjl
		join `tabUkuran Berat Jenis Limas Detail` bjld on bjl.name = bjld.parent
		where bjl.pabrik = %s and bjl.kompartemen = %s and bjld.density = %s 
	""",(pabrik,kompartemen,density),as_dict=True)

	return query[0].berat if query else 0 