# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate,flt
from frappe.model.mapper import get_mapped_doc

from sth.mill.rekap_sounding import hitung_ulang_dokumen_sesudahnya, hitung_ulang_rekap
from sth.mill.utils import get_adjustment_stock, get_potongan_sortasi, set_rata_rata_rendemen_bulanan

class SoundingStockPalmKerneldiBunkerKernel(Document):
	def onload(self):
		set_rata_rata_rendemen_bulanan(self)

	def before_save(self):
		self.hasil_titik_sounding = []

		if self.ukuran_detail:
			self.calculate_hasil_titik_sounding()
			self.add_rekap_hasil()
		
		self.calculate_volume_sounding()
		# self.produksi = self.volume_sounding - self.stock_akhir 
		# self.ker_netto_1 = self.produksi / self.tbs_olah*100 if self.tbs_olah else 0 
		# self.ker_netto_2 = self.produksi/(self.tbs_olah - self.sortasi)*100 if self.tbs_olah else 0

	def before_submit(self):
		self.validate_minus_value()

	def validate(self):
		# minta dipindah sebelum submit dari Rezky - 17-09
		# self.validate_minus_value()
		self.hitung_produksi()
		set_rata_rata_rendemen_bulanan(self)

	def hitung_produksi(self):
		self.stock_akhir = self.volume_sounding
		self.produksi = flt(self.stock_akhir) - flt(self.stock_awal) + flt(self.pengiriman)
		self.hitung_ker_netto()

	def hitung_ker_netto(self):
		"""KER netto 1 dan 2 dari produksi, tbs olah, dan potongan sortasi.

		Dipisah dari hitung_produksi supaya bisa dihitung ulang sendirian tanpa
		ikut menyentuh produksi — produksi sudah jadi Stock Entry waktu dokumennya
		disubmit, jadi patch yang cuma membetulkan rendemen tidak boleh
		menggesernya. Sejajar dengan calculate_oer_netto di Sounding CPO.
		"""
		self.ker_netto_1 = self.produksi / self.tbs_olah*100 if self.tbs_olah else 0

		# Dua penjaga sekaligus. Penyebut nol: seluruh TBS yang masuk kena potongan
		# sortasi, tbs_olah terisi tapi selisihnya nol dan pembagiannya error.
		# tbs_olah nol: potongan sortasinya sedang menumpuk untuk hari olah
		# berikutnya, jadi penyebutnya negatif dan hasilnya KER minus yang tidak
		# berarti apa-apa selain menahan submit lewat validate_minus_value.
		penyebut_netto_2 = flt(self.tbs_olah) - flt(self.sortasi)
		self.ker_netto_2 = (
			self.produksi / penyebut_netto_2 * 100
			if (flt(self.tbs_olah) and penyebut_netto_2)
			else 0
		)

	def on_submit(self):
		self.create_ste()
		self.update_document_afterwards()

	def on_cancel(self):
		ste = frappe.db.get_all("Stock Entry",{"references": self.name})
		for row in ste:
			doc = frappe.get_doc("Stock Entry",row)
			if doc.docstatus == 1:
				doc.cancel()

		self.update_document_afterwards()

	def update_document_afterwards(self):
		"""Sounding sesudah dokumen ini ikut dihitung ulang.

		Sebelumnya tidak ada sama sekali di sini, padahal Palm Kernel punya
		rantai yang sama dengan CPO: produksi dokumen ini jadi Stock Entry, dan
		Stock Entry itu yang membentuk stock awal dokumen sesudahnya lewat
		get_stock_awal. Sounding bertanggal mundur karena itu tidak pernah
		menggeser hari-hari sesudahnya.
		"""
		hitung_ulang_dokumen_sesudahnya(self)

	@frappe.whitelist()
	def hitung_ulang(self):
		"""Tombol Hitung Ulang: dokumen ini sendiri ikut, bukan cuma sesudahnya.

		Yang dikejar pengiriman Palm Kernel atau koreksi stok yang masuk sesudah
		dokumen ini disubmit — itu menggeser rekap dokumen ini sendiri, bukan
		cuma dokumen sesudahnya.
		"""
		return hitung_ulang_rekap(self.doctype, self.unit, self.tanggal_proses)
	
	def on_trash(self):
		ste = frappe.db.get_all("Stock Entry",{"references": self.name})
		for row in ste:
			doc = frappe.get_doc("Stock Entry",row)
			doc.delete()

	def validate_minus_value(self):
		if flt(self.produksi) < 0 or flt(self.ker_netto_1) < 0 or flt(self.ker_netto_2) < 0 or flt(self.rata_rata_ker_bulanan) < 0 or flt(self.total_produksi_bulanan) < 0:
			frappe.throw(f"Produksi PK/KER tidak boleh minus")

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
		if self.ignore_recalculate: return

		self.rekap_hasil = []
		for row in self.hasil_titik_sounding:
			parent_doc = frappe.db.get_value("Ukuran Bunker Kernel Silo",{"pabrik":self.pabrik,"kompartemen_bunker":row.nama_kompartemen_bunker}) or frappe.db.get_value("Ukuran Bunker Kernel Silo",{"pabrik":self.pabrik,"default":1})

			tonase,liter = frappe.get_value("Ukuran Bunker Kernel Silo Detail",{"parent": parent_doc,"ukuran":row.total_hitungan, },["tonase","liter"]) or (0,0)

			volume = tonase * 1000 if flt(tonase) > 0 else liter

			self.append("rekap_hasil",{
				"kompartemen": row.nama_kompartemen_bunker,
				"ukuran": flt(row.total_hitungan),
				"volume": flt(volume),
				"netto" : flt(volume * self.berat_jenis if self.berat_jenis > 0 else volume)
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

		self.stock_awal = self.get_stock_awal()
		self.set_adjustment()
		self.pengiriman = get_delivery[0].qty if get_delivery else 0
		# Disaring pabrik, sama dengan Sounding CPO. Tanpa saringan itu
		# get_value memulangkan Data TBS mana saja yang tanggalnya cocok, jadi
		# pabrik yang soundingnya dihitung belakangan bisa memakai tbs olah
		# milik pabrik lain — dan KER-nya ikut salah.
		self.tbs_olah = frappe.db.get_value("Data TBS",{"tanggal_produksi":self.tanggal_proses,"pabrik":self.pabrik},"tbs_olah") or 0
		# Bukan cuma sortasi hari ini: hari yang pabriknya tidak mengolah ikut
		# terkumpul sampai ada olah. Rinciannya di get_potongan_sortasi.
		self.sortasi = get_potongan_sortasi(self.unit, self.tanggal_proses, self.pabrik)

		# Stock akhir dan produksinya dihitung dengan rumus yang sama seperti waktu
		# dokumen disimpan, supaya angka yang muncul begitu tombol ditekan tidak
		# berubah lagi setelah disimpan. Dipanggil paling akhir karena KER-nya
		# memakai tbs olah dan sortasi yang baru diisi di atas.
		self.hitung_produksi()

	def set_adjustment(self):
		"""Pecah stock awal jadi bagian sebelum koreksi dan koreksinya sendiri.

		Sekadar keterangan: produksi dan KER tetap dihitung dari stock_awal yang
		utuh, yaitu yang sudah termasuk adjustment. Stock awal di sini saldo
		pembuka hari itu, jadi yang dihitung koreksi sebelum tanggal proses saja.
		"""
		self.adjustment = get_adjustment_stock(
			frappe.db.get_value("Item", {"tipe_barang": "Palm Kernel"}),
			get_warehouse_palm(self.unit),
			self.unit,
			self.doctype,
			self.tanggal_proses,
		)
		self.stock_awal_sebelum_adjustment = flt(self.stock_awal) - flt(self.adjustment)

	def get_stock_awal(self):
		"""Saldo Palm Kernel dari Stock Ledger Entry terakhir sebelum tanggal proses.

		Yang dibaca qty_after_transaction baris paling akhir sebelum tanggal proses
		di gudang unit ini — saldo pembuka hari itu, jadi mutasi pada tanggal
		prosesnya sendiri tidak ikut. Entry batal tidak dihitung.
		"""
		warehouse = get_warehouse_palm(self.unit)
		item_code = frappe.db.get_value("Item",{"tipe_barang": "Palm Kernel"})

		if not (warehouse and item_code):
			return 0

		terakhir = frappe.db.sql("""
			select qty_after_transaction
			from `tabStock Ledger Entry`
			where item_code = %s and warehouse = %s and is_cancelled = 0
				and posting_date < %s
			order by posting_date desc, posting_time desc, creation desc
			limit 1
		""",(item_code, warehouse, self.tanggal_proses))

		return flt(terakhir[0][0]) if terakhir else 0

	def split_and_avg(self,arr):
		arr = list(map(int, arr))
		mid = len(arr) // 2
		
		left = arr[:mid + (len(arr) % 2)]
		right = arr[mid:]
		
		return sum(left)/len(left), sum(right)/len(right)
	
	def create_ste(self):
		# Penjaganya pindah ke sini dari on_submit. Selama ada di on_submit,
		# tiap jalur yang membuat ulang Stock Entry — tombol Hitung Ulang,
		# job sesudah Timbangan, patch — harus ingat sendiri untuk mengulang
		# syarat yang sama, dan yang lupa akan membuatkan Material Receipt
		# sebesar angka minus untuk dokumen yang waktu disubmit tidak dibuatkan
		# apa-apa. Sejajar dengan create_ste Sounding CPO yang juga menjaga
		# sendiri, bedanya CPO memang mengeluarkan Material Issue untuk minus.
		if flt(self.produksi) <= 0: return

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
					"tanggal_proses":"posting_date",
					"jam":"posting_time"
				}
			},
		}

		# posting_date diambil dari tanggal_proses, bukan field tanggal: tanggal
		# adalah kapan soundingnya dicatat, sementara produksinya milik hari
		# prosesnya — sama seperti stock awal, pengiriman, dan tbs olah yang
		# semuanya diambil per tanggal_proses di get_stock(). Jamnya ikut field
		# jam, jadi urutan Stock Ledger di hari itu ikut jam soundingnya.
		doc = get_mapped_doc(self.doctype,self.name,mapper,None,postprocess,True)
		# Tanpa ini validate_posting_time menimpa posting_date dengan hari ini.
		doc.set_posting_time = 1
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