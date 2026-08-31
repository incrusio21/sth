# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import erpnext
import frappe
from erpnext.accounts.general_ledger import make_gl_entries, make_reverse_gl_entries
from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import (
	EmptyStockReconciliationItemsError,
)
from frappe.model.document import Document
from frappe.utils import add_days, flt

# Produk dikenali lewat Item.tipe_barang. Gudangnya ikut Default Warehouse di
# Item Defaults item itu sendiri, bukan Warehouse Category.
TIPE_BARANG = {"TBS": "TBS", "CPO": "CPO", "Palm Kernel": "Palm Kernel"}

PREFIKS = {"TBS": "tbs", "CPO": "cpo", "Palm Kernel": "pk"}

VOUCHER_PEMBELIAN = ("Purchase Receipt", "Purchase Invoice")
VOUCHER_PENJUALAN = ("Delivery Note", "Sales Invoice")
VOUCHER_ADJUSTMENT = "Stock Reconciliation"

# Biaya Mill = total kepala akun 63 (Proses Pabrik) dan 72 (Biaya Tidak
# Langsung). Dipakai patch isi_sumber_biaya_mill_cogs untuk mengisi tabel COGS
# Sumber Biaya; sesudah terisi, yang dibaca tetap tabel setelannya, jadi
# kepala akun lain bisa ditambah atau dibuang dari sana tanpa mengubah kode.
KEPALA_AKUN_MILL = ("63", "72")

# Susunan baris rincian, mengikuti urutan di Formula COGS Mill dan Kebun.xlsx.
BARIS = (
	("tbs_opening", "TBS", "Opening Stock"),
	("tbs_production", "TBS", "Production"),
	("tbs_purchase", "TBS", "FFB Purchase"),
	("tbs_available", "TBS", "Available"),
	("tbs_closing", "TBS", "Closing Stock"),
	("tbs_cop", "TBS", "Cost Of Production"),
	("tbs_sold", "TBS", "Sold to Third Parties"),
	("tbs_internal", "TBS", "Internal Consumption"),
	("cpo_opening", "CPO", "Opening Stock"),
	("cpo_purchase", "CPO", "Purchase"),
	("cpo_production", "CPO", "Production"),
	("cpo_available", "CPO", "Available"),
	("cpo_adjustment", "CPO", "Stock Adjustment"),
	("cpo_closing", "CPO", "Closing Stock"),
	("cpo_cogs", "CPO", "Cost Of Goods Sold"),
	("pk_opening", "Palm Kernel", "Opening Stock"),
	("pk_purchase", "Palm Kernel", "Purchase"),
	("pk_production", "Palm Kernel", "Production"),
	("pk_available", "Palm Kernel", "Available"),
	("pk_adjustment", "Palm Kernel", "Stock Adjustment"),
	("pk_closing", "Palm Kernel", "Closing Stock"),
	("pk_cogs", "Palm Kernel", "Cost Of Goods Sold"),
)

# Dokumen sumber angka posisi tiap produk. Doctype-nya beda-beda tapi polanya
# sama: satu dokumen per unit per hari, qty produksi dan stok akhir ada di
# field-nya sendiri, dan Stock Entry yang dibuatnya menempelkan nama dokumen di
# field references. Stock Ledger tidak dipakai untuk angka-angka ini karena
# Stock Entry-nya cuma memposting selisih, bukan posisi.
#
# 'produksi_total' membedakan jumlah sepanjang periode dari posisi terakhir;
# ketiganya sekarang dijumlahkan, yang memakai posisi terakhir tinggal Closing.
# Field produksi CPO dan PK sengaja yang sama dengan qty Stock Entry bikinan
# Sounding, jadi qty dan rate-nya berasal dari angka yang sama.
SUMBER_PRODUK = {
	"tbs": {
		"doctype": "Data TBS",
		"tanggal": "tanggal_produksi",
		"produksi": "tbs_olah",
		"produksi_total": True,
		"closing": "jumlah_tbs_restan",
	},
	"cpo": {
		"doctype": "Sounding Stock CPO di BST",
		"tanggal": "tanggal_proses",
		"produksi": "produksi_cpo",
		"produksi_total": True,
		"closing": "stock_bst",
	},
	"pk": {
		"doctype": "Sounding Stock Palm Kernel di Bunker Kernel",
		"tanggal": "tanggal_proses",
		"produksi": "produksi",
		"produksi_total": True,
		"closing": "stock_akhir",
	},
}

WAKTU_REKONSILIASI = "23:59:59"

KETERANGAN_KEBUN = "KAPITALISASI BIAYA KEBUN KE PERSEDIAAN TBS"
KETERANGAN_OLAH = "PENGOLAHAN TBS MENJADI CPO DAN PALM KERNEL"
KETERANGAN_HPP = "HARGA POKOK PENJUALAN {0}"


class COGSMilldanKebun(Document):

	def validate(self):
		self.validasi_periode()
		self.validasi_mode_posting()
		self.hitung()

	def on_submit(self):
		if self.buat_stock_reconciliation:
			self.buat_rekonsiliasi()
			return
		if not self.posting_jurnal:
			frappe.msgprint(
				"Tabel Closing sudah tersusun tapi tidak diposting ke buku besar karena "
				"<b>Posting Jurnal ke Buku Besar</b> masih mati.",
				indicator="orange",
				alert=True,
			)
			return
		self.make_gl_entry()

	def on_cancel(self):
		self.ignore_linked_doctypes = ("GL Entry",)
		self.batalkan_rekonsiliasi()
		if not self.posting_jurnal:
			return
		self.make_gl_entry()

	def on_trash(self):
		frappe.db.delete("GL Entry", {
			"voucher_type": self.doctype,
			"voucher_no": self.name,
		})

	# ------------------------------------------------------------------
	# Validasi
	# ------------------------------------------------------------------

	def validasi_periode(self):
		if self.periode_dari and self.periode_sampai and self.periode_dari > self.periode_sampai:
			frappe.throw("Periode Dari tidak boleh melewati Periode Sampai.")

		filters = {
			"company": self.company,
			"periode_dari": self.periode_dari,
			"periode_sampai": self.periode_sampai,
			"docstatus": ("<", 2),
			"name": ("!=", self.name),
		}
		filters["unit"] = self.unit if self.unit else ("is", "not set")

		kembar = frappe.db.exists("COGS Mill dan Kebun", filters)
		if kembar:
			frappe.throw(
				"Periode ini sudah punya dokumen <b>{0}</b>.".format(kembar),
				title="Duplikat Tidak Diizinkan",
			)

	def validasi_mode_posting(self):
		"""Stock Reconciliation dan jurnal Closing sama-sama menyentuh akun
		persediaan, jadi kalau keduanya jalan nilainya dobel."""
		if self.buat_stock_reconciliation and self.posting_jurnal:
			frappe.throw(
				"<b>Buat Stock Reconciliation saat Submit</b> dan <b>Posting Jurnal ke Buku "
				"Besar</b> tidak bisa menyala bersamaan karena keduanya sama-sama menjurnal "
				"akun persediaan. Pilih salah satu.",
				title="Dua Sumber Jurnal Persediaan",
			)

	# ------------------------------------------------------------------
	# Perhitungan
	# ------------------------------------------------------------------

	@frappe.whitelist()
	def ambil_data(self):
		"""Isi ulang rincian dari dokumen sumber lalu langsung hitung turunannya.

		Dipanggil lewat frm.call dengan dokumennya ikut dikirim, mengikuti pola
		Costing Kebun. Sebelumnya tombol ini cuma mengisi baris masukan lewat
		fungsi modul, jadi Available, Cost Of Production, dan Internal Consumption
		tetap nol sampai dokumennya disimpan dan hasilnya kelihatan seperti salah.

		Mengembalikan daftar peringatan; baris turunannya ikut terkirim balik
		bersama dokumen.
		"""
		if not (self.periode_dari and self.periode_sampai):
			frappe.throw("Harap isi Periode Dari dan Periode Sampai terlebih dahulu.")

		if not self.company:
			frappe.throw("Harap isi Company terlebih dahulu.")

		data = ambil_data(self.periode_dari, self.periode_sampai, self.company, self.unit)

		for fieldname in (
			"biaya_kebun",
			"biaya_mill",
			"harga_rata_cpo",
			"harga_rata_pk",
			"saldo_gl_tbs",
			"saldo_gl_cpo",
			"saldo_gl_pk",
		):
			self.set(fieldname, data[fieldname])

		self.set("rincian", [])
		for row in data["rincian"]:
			self.append("rincian", row)

		self.hitung()

		return data["peringatan"]

	def hitung(self):
		"""Hitung ulang seluruh baris turunan, conversion cost, dan jurnal.

		Baris masukan (Opening, Purchase, dan qty Closing/Sold/Adjustment)
		dipertahankan apa adanya supaya bisa dikoreksi manual di grid.
		"""
		nilai = {}
		for row in self.rincian:
			if row.kode:
				nilai[row.kode] = {"qty": flt(row.qty), "amount": flt(row.amount)}

		def q(kode):
			return flt(nilai.get(kode, {}).get("qty"))

		def a(kode):
			return flt(nilai.get(kode, {}).get("amount"))

		def isi(kode, qty=None, amount=None):
			baris = nilai.setdefault(kode, {"qty": 0.0, "amount": 0.0})
			if qty is not None:
				baris["qty"] = flt(qty)
			if amount is not None:
				baris["amount"] = flt(amount)

		# Rate tiap produk dibaca ulang dari Stock Entry dokumen sumbernya, tidak
		# disimpan di field: nilainya harus selalu sama dengan yang dipakai Stock
		# Ledger, jadi tidak boleh ada yang mengetiknya sendiri di form.
		rate = {}
		if self.company and self.periode_dari and self.periode_sampai:
			for produk, prefiks in PREFIKS.items():
				rate[prefiks] = rate_dari_stock_entry(
					prefiks, produk, self.company, self.unit,
					self.periode_dari, self.periode_sampai,
				)

		# --- TBS: satu rate untuk semua baris, jadi Available di sisi rupiah
		# otomatis sejalan dengan qty-nya.
		rate_tbs = flt(rate.get("tbs"))
		for kode in ("tbs_opening", "tbs_production", "tbs_purchase"):
			isi(kode, amount=rate_tbs * q(kode))
		isi(
			"tbs_available",
			qty=q("tbs_opening") + q("tbs_production") + q("tbs_purchase"),
			amount=a("tbs_opening") + a("tbs_production") + a("tbs_purchase"),
		)
		# Closing dan Sold TBS disimpan negatif lalu dijumlahkan, mengikuti excel.
		isi("tbs_closing", amount=rate_tbs * q("tbs_closing"))
		isi(
			"tbs_cop",
			qty=q("tbs_available") + q("tbs_closing"),
			amount=a("tbs_available") + a("tbs_closing"),
		)
		isi("tbs_sold", amount=rate_tbs * q("tbs_sold"))
		isi(
			"tbs_internal",
			qty=q("tbs_cop") + q("tbs_sold"),
			amount=a("tbs_cop") + a("tbs_sold"),
		)

		# --- Conversion cost: OER dan KER dari qty produksi terhadap TBS diolah
		self.qty_tbs_diolah = q("tbs_internal")
		self.oer = (q("cpo_production") / self.qty_tbs_diolah * 100) if self.qty_tbs_diolah else 0
		self.ker = (q("pk_production") / self.qty_tbs_diolah * 100) if self.qty_tbs_diolah else 0

		nilai_cpo = flt(self.oer) * flt(self.harga_rata_cpo)
		nilai_pk = flt(self.ker) * flt(self.harga_rata_pk)
		pembagi = nilai_cpo + nilai_pk

		# Conversion cost sekarang angka pemantau saja. Nilai produksi CPO dan PK
		# tidak lagi dibagi dari TBS diolah plus biaya mill, tapi diambil dari
		# rate Stock Entry Sounding masing-masing.
		self.conversion_cost_cpo = (nilai_cpo / pembagi * 100) if pembagi else 0
		self.conversion_cost_pk = (100 - flt(self.conversion_cost_cpo)) if pembagi else 0

		# --- CPO dan PK: Production dari rate Sounding, sisanya rata-rata
		# tertimbang. Closing negatif seperti TBS, jadi COGS menjumlahkan.
		for prefiks in ("cpo", "pk"):
			isi(prefiks + "_production", amount=flt(rate.get(prefiks)) * q(prefiks + "_production"))
			isi(
				prefiks + "_available",
				qty=q(prefiks + "_opening") + q(prefiks + "_production") + q(prefiks + "_purchase"),
				amount=a(prefiks + "_opening") + a(prefiks + "_production") + a(prefiks + "_purchase"),
			)
			rate_rata = (
				a(prefiks + "_available") / q(prefiks + "_available")
				if q(prefiks + "_available")
				else 0
			)
			# Selisih nilai stock adjustment sengaja tidak dijurnal, mengikuti
			# excel: qty-nya menambah COGS, nilainya terserap lewat rate.
			isi(prefiks + "_adjustment", amount=0)
			isi(prefiks + "_closing", amount=rate_rata * q(prefiks + "_closing"))
			isi(
				prefiks + "_cogs",
				qty=q(prefiks + "_available") + q(prefiks + "_adjustment") + q(prefiks + "_closing"),
				amount=a(prefiks + "_available") + a(prefiks + "_adjustment") + a(prefiks + "_closing"),
			)

		self.tulis_rincian(nilai)
		self.susun_closing(nilai)
		self.susun_rekonsiliasi(nilai)
		self.hitung_selisih_gl(nilai)

	def tulis_rincian(self, nilai):
		self.set("rincian", [])
		for kode, produk, label in BARIS:
			baris = nilai.get(kode) or {"qty": 0.0, "amount": 0.0}
			qty = flt(baris["qty"])
			amount = flt(baris["amount"], 2)
			self.append("rincian", {
				"kode": kode,
				"produk": produk,
				"baris": label,
				"qty": qty,
				"amount": amount,
				"rate": (amount / qty) if qty else 0,
			})

	def hitung_selisih_gl(self, nilai):
		"""Informasi saja: saldo GL akun persediaan setelah jurnal dokumen ini
		dibandingkan dengan nilai Closing Stock hasil perhitungan."""

		def a(kode):
			return flt(nilai.get(kode, {}).get("amount"))

		# Closing dan Sold disimpan negatif di ketiga produk, jadi ikut
		# dijumlahkan, bukan dikurangkan.
		self.selisih_gl_tbs = flt(
			flt(self.saldo_gl_tbs)
			+ a("tbs_production")
			- a("tbs_internal")
			+ a("tbs_sold")
			+ a("tbs_closing"),
			2,
		)
		for prefiks in ("cpo", "pk"):
			self.set(
				"selisih_gl_" + prefiks,
				flt(
					flt(self.get("saldo_gl_" + prefiks))
					+ a(prefiks + "_production")
					- a(prefiks + "_cogs")
					+ a(prefiks + "_closing"),
					2,
				),
			)

	# ------------------------------------------------------------------
	# Stock Reconciliation
	# ------------------------------------------------------------------

	def susun_rekonsiliasi(self, nilai):
		"""Daftar gudang yang akan disamakan nilainya, disusun sejak draft
		supaya bisa diperiksa sebelum submit. Nama Stock Reconciliation-nya
		baru terisi waktu submit, jadi yang sudah ada dipertahankan."""
		sebelumnya = {
			(row.item_code, row.gudang): row.stock_reconciliation
			for row in self.get("rekonsiliasi") or []
			if row.stock_reconciliation
		}

		self.set("rekonsiliasi", [])
		if not self.buat_stock_reconciliation or not self.company or not self.periode_sampai:
			return

		def rate_produk(prefiks):
			# Rate Closing Stock; kalau tidak ada stok akhir, rate Available
			# dipakai supaya gudang yang masih menyimpan barang tetap punya
			# nilai satuan yang sama dengan periode ini.
			for akhiran in ("_closing", "_available"):
				baris = nilai.get(prefiks + akhiran) or {}
				if flt(baris.get("qty")) and flt(baris.get("amount")):
					return flt(baris["amount"]) / flt(baris["qty"])
			return 0.0

		tanpa_rate = []
		for produk, prefiks in PREFIKS.items():
			rate = rate_produk(prefiks)
			for item_code in get_item_produk(produk):
				for gudang, unit in gudang_berstok(
					item_code, self.company, self.unit, self.periode_sampai
				):
					qty, nilai_stok = saldo_sle(item_code, gudang, self.periode_sampai)
					if not qty and not nilai_stok:
						continue
					if qty and not rate:
						# Menilai barang yang masih ada dengan rate nol akan
						# menghapus nilainya, jadi produknya dilewat saja.
						if produk not in tanpa_rate:
							tanpa_rate.append(produk)
						continue
					# Gudang kosong bernilai nol; rate hanya dipasang kalau
					# masih ada barangnya.
					rate_baris = flt(rate) if qty else 0.0
					if flt(nilai_stok, 2) == flt(rate_baris * qty, 2):
						continue
					self.append("rekonsiliasi", {
						"produk": produk,
						"item_code": item_code,
						"gudang": gudang,
						"unit": unit or self.unit,
						"qty": qty,
						"rate": rate_baris,
						"amount": flt(rate_baris * qty, 2),
						"stock_reconciliation": sebelumnya.get((item_code, gudang)),
					})

		if tanpa_rate:
			frappe.msgprint(
				"Rate Closing Stock <b>{0}</b> nol padahal gudangnya masih menyimpan barang, "
				"jadi produk itu tidak ikut direkonsiliasi.".format(", ".join(tanpa_rate)),
				indicator="orange",
				alert=True,
			)

	def buat_rekonsiliasi(self):
		if not self.get("rekonsiliasi"):
			frappe.msgprint(
				"Tidak ada gudang yang perlu direkonsiliasi: nilai persediaannya sudah sama "
				"dengan rate Closing Stock periode ini.",
				indicator="orange",
				alert=True,
			)
			return

		setelan = get_setelan(self.company) or frappe._dict()

		tanpa_unit = sorted({row.gudang for row in self.rekonsiliasi if not row.unit})
		if tanpa_unit:
			frappe.throw(
				"Gudang berikut belum punya Unit, padahal Stock Reconciliation mewajibkannya: "
				"<b>{0}</b>.".format(", ".join(tanpa_unit))
			)

		# Satu Stock Reconciliation per produk per unit: cost center-nya beda
		# antara kebun dan mill, dan Unit wajib diisi satu nilai per dokumen.
		kelompok = {}
		for row in self.rekonsiliasi:
			kelompok.setdefault((row.produk, row.unit), []).append(row)

		tanpa_akun = sorted({
			produk for produk, _unit in kelompok if not self.akun_selisih(setelan, produk)
		})
		if tanpa_akun:
			frappe.throw(
				"Lawan jurnal rekonsiliasi untuk <b>{0}</b> belum ada. Isi <b>Akun Selisih "
				"Rekonsiliasi</b> di STH Accounting Settings tab COGS untuk company <b>{1}</b>, "
				"atau lengkapi akun alokasinya.".format(", ".join(tanpa_akun), self.company)
			)

		dibuat = []
		for (produk, unit), baris in kelompok.items():
			nama = self.submit_stock_reconciliation(setelan, produk, unit, baris)
			if not nama:
				continue
			dibuat.append(nama)
			for row in baris:
				row.stock_reconciliation = nama
				frappe.db.set_value(
					row.doctype, row.name, "stock_reconciliation", nama, update_modified=False
				)

		if dibuat:
			frappe.msgprint(
				"Stock Reconciliation <b>{0}</b> berhasil dibuat.".format(", ".join(sorted(dibuat))),
				indicator="green",
				alert=True,
			)

	def akun_selisih(self, setelan, produk):
		"""Lawan jurnal Stock Reconciliation.

		Kalau field khususnya kosong, dipakai akun alokasi produk itu — akun yang
		dulu dikredit tabel Closing. Selisih penilaiannya jadi menutup biaya kebun
		atau biaya mill periode ini, bukan lahir sebagai untung-rugi baru.
		"""
		if setelan.akun_selisih_rekonsiliasi:
			return setelan.akun_selisih_rekonsiliasi
		return setelan.akun_alokasi_kebun if produk == "TBS" else setelan.akun_alokasi_pabrik

	def submit_stock_reconciliation(self, setelan, produk, unit, baris):
		sr = frappe.new_doc("Stock Reconciliation")
		sr.purpose = "Stock Reconciliation"
		sr.company = self.company
		sr.unit = unit
		sr.set_posting_time = 1
		sr.posting_date = self.periode_sampai
		sr.posting_time = WAKTU_REKONSILIASI
		sr.expense_account = self.akun_selisih(setelan, produk)
		sr.cost_center = (
			setelan.cost_center_kebun if produk == "TBS" else setelan.cost_center_mill
		)

		for row in baris:
			sr.append("items", {
				"item_code": row.item_code,
				"warehouse": row.gudang,
				"qty": flt(row.qty),
				"valuation_rate": flt(row.rate),
			})

		# Kalau ternyata ERPNext menilai tidak ada baris yang berubah, dokumennya
		# batal dibuat tanpa menghentikan submit COGS-nya.
		batas_pesan = len(frappe.local.message_log)
		try:
			sr.insert(ignore_permissions=True)
			sr.submit()
		except EmptyStockReconciliationItemsError:
			del frappe.local.message_log[batas_pesan:]
			return None

		return sr.name

	def batalkan_rekonsiliasi(self):
		nama = []
		for row in self.get("rekonsiliasi") or []:
			if row.stock_reconciliation and row.stock_reconciliation not in nama:
				nama.append(row.stock_reconciliation)

		dibatalkan = []
		for sr in nama:
			if frappe.db.get_value("Stock Reconciliation", sr, "docstatus") == 1:
				frappe.get_doc("Stock Reconciliation", sr).cancel()
				dibatalkan.append(sr)

		if dibatalkan:
			frappe.msgprint(
				"Stock Reconciliation <b>{0}</b> ikut dibatalkan.".format(", ".join(dibatalkan)),
				indicator="orange",
				alert=True,
			)

	# ------------------------------------------------------------------
	# Jurnal
	# ------------------------------------------------------------------

	def susun_closing(self, nilai):
		# Setelan yang belum lengkap tidak menghentikan penyusunan tabel: baris
		# jurnalnya tetap dibentuk dengan kolom akun kosong supaya nilainya bisa
		# diperiksa lebih dulu. Yang menuntut akun lengkap cuma posting.
		setelan = get_setelan(self.company) or frappe._dict()

		if self.docstatus == 1 and self.posting_jurnal and not setelan:
			frappe.throw(
				"Company <b>{0}</b> belum punya baris di tabel COGS pada "
				"STH Accounting Settings, jadi jurnalnya tidak bisa diposting.".format(self.company)
			)

		def a(kode):
			return flt(nilai.get(kode, {}).get("amount"), 2)

		cc_kebun = setelan.cost_center_kebun
		cc_mill = setelan.cost_center_mill

		baris = []

		def tambah(akun, cost_center, debit, credit, keterangan):
			if not flt(debit, 2) and not flt(credit, 2):
				return
			baris.append({
				"no_coa": akun,
				"cost_center": cost_center,
				"debit": flt(debit, 2),
				"credit": flt(credit, 2),
				"keterangan": keterangan,
			})

		# 1. Biaya kebun dikapitalisasi jadi nilai persediaan TBS
		tambah(setelan.akun_persediaan_tbs, cc_kebun, a("tbs_production"), 0, KETERANGAN_KEBUN)
		tambah(setelan.akun_alokasi_kebun, cc_kebun, 0, a("tbs_production"), KETERANGAN_KEBUN)

		# 2. TBS yang diolah plus biaya mill pindah ke persediaan CPO dan PK
		tambah(setelan.akun_persediaan_cpo, cc_mill, a("cpo_production"), 0, KETERANGAN_OLAH)
		tambah(setelan.akun_persediaan_pk, cc_mill, a("pk_production"), 0, KETERANGAN_OLAH)
		tambah(setelan.akun_persediaan_tbs, cc_mill, 0, a("tbs_internal"), KETERANGAN_OLAH)
		tambah(setelan.akun_alokasi_pabrik, cc_mill, 0, flt(self.biaya_mill, 2), KETERANGAN_OLAH)

		# 3. Harga pokok penjualan masing-masing produk
		tambah(setelan.akun_hpp_tbs, cc_kebun, a("tbs_sold"), 0, KETERANGAN_HPP.format("TBS"))
		tambah(setelan.akun_persediaan_tbs, cc_kebun, 0, a("tbs_sold"), KETERANGAN_HPP.format("TBS"))
		tambah(setelan.akun_hpp_cpo, cc_mill, a("cpo_cogs"), 0, KETERANGAN_HPP.format("CPO"))
		tambah(setelan.akun_persediaan_cpo, cc_mill, 0, a("cpo_cogs"), KETERANGAN_HPP.format("CPO"))
		tambah(setelan.akun_hpp_pk, cc_mill, a("pk_cogs"), 0, KETERANGAN_HPP.format("PALM KERNEL"))
		tambah(setelan.akun_persediaan_pk, cc_mill, 0, a("pk_cogs"), KETERANGAN_HPP.format("PALM KERNEL"))

		if self.docstatus == 1 and self.posting_jurnal:
			kurang = sorted({row["keterangan"] for row in baris if not row["no_coa"]})
			if kurang:
				frappe.throw(
					"Akun untuk jurnal berikut belum diisi di STH Accounting Settings: "
					"<b>{0}</b>".format(", ".join(kurang))
				)

		self.set("closing", [])
		for row in baris:
			self.append("closing", row)

		# Kedua sisi dijumlahkan sendiri-sendiri, bukan satu total: sejak nilai
		# produksi CPO dan PK diambil dari rate Sounding, debit dan kredit tidak
		# lagi otomatis ketemu dan bedanya perlu kelihatan.
		self.total_closing = sum(flt(row["debit"]) for row in baris)
		self.total_credit = sum(flt(row["credit"]) for row in baris)

	def make_gl_entry(self):
		if self.docstatus == 1:
			make_gl_entries(self.get_gl_entries(), merge_entries=False)
		elif self.docstatus == 2:
			make_reverse_gl_entries(voucher_type=self.doctype, voucher_no=self.name)

	def get_gl_entries(self):
		gl_entries = []
		default_cost_center = erpnext.get_default_cost_center(self.company)

		total_debit = 0
		total_credit = 0

		for row in self.closing:
			cost_center = row.cost_center or default_cost_center

			if row.debit:
				total_debit += flt(row.debit)
				gl_entries.append(self.get_gl_dict({
					"account": row.no_coa,
					"cost_center": cost_center,
					"debit": row.debit,
					"debit_in_account_currency": row.debit,
					"remarks": row.keterangan,
				}))
			if row.credit:
				total_credit += flt(row.credit)
				gl_entries.append(self.get_gl_dict({
					"account": row.no_coa,
					"cost_center": cost_center,
					"credit": row.credit,
					"credit_in_account_currency": row.credit,
					"remarks": row.keterangan,
				}))

		if gl_entries and flt(total_debit, 2) != flt(total_credit, 2):
			frappe.throw(
				"Debit ({0}) dan Kredit ({1}) di tabel Closing tidak seimbang. "
				"Jalankan ulang Ambil Data.".format(flt(total_debit, 2), flt(total_credit, 2))
			)

		return gl_entries

	def get_gl_dict(self, args):
		gl_dict = frappe._dict({
			"company": self.company,
			"posting_date": self.periode_sampai,
			"voucher_type": self.doctype,
			"voucher_no": self.name,
			"remarks": "COGS Mill dan Kebun {0}".format(self.name),
			"against": None,
			"debit": 0,
			"credit": 0,
			"debit_in_account_currency": 0,
			"credit_in_account_currency": 0,
			"is_opening": "No",
			"party_type": None,
			"party": None,
			"cost_center": None,
			"company_currency": erpnext.get_company_currency(self.company),
		})
		gl_dict.update(args)
		return gl_dict


# ---------------------------------------------------------------------------
# Setelan, Item, dan Gudang
# ---------------------------------------------------------------------------

def get_setelan(company):
	if not company:
		return None
	setelan = frappe.get_single("STH Accounting Settings")
	for row in setelan.get("sth_accounting_settings_cogs") or []:
		if row.company == company:
			return row
	return None


def get_sumber_biaya(company, kelompok):
	setelan = frappe.get_single("STH Accounting Settings")
	return [
		row.akun
		for row in setelan.get("sth_accounting_settings_cogs_sumber_biaya") or []
		if row.company == company and row.kelompok == kelompok and row.akun
	]


def get_item_produk(produk):
	"""Semua item dengan tipe barang ini. Satu produk boleh punya lebih dari
	satu item, jadi hasilnya daftar dan angkanya dijumlahkan."""
	return frappe.get_all(
		"Item",
		filters={"tipe_barang": TIPE_BARANG[produk], "disabled": 0},
		pluck="name",
		order_by="name",
	)


def gudang_berstok(item_code, company, unit, sampai):
	"""Semua gudang company ini yang pernah dilewati item, termasuk gudang
	transit. Yang dipakai rekonsiliasi bukan cuma gudang default karena nilai
	satuan barang harus sama di mana pun barangnya berada."""
	rows = frappe.db.sql("""
		select distinct sle.warehouse as gudang, w.unit as unit
		from `tabStock Ledger Entry` sle
		inner join `tabWarehouse` w on w.name = sle.warehouse
		where sle.item_code = %s and sle.posting_date <= %s and sle.is_cancelled = 0
			and w.company = %s
		order by sle.warehouse
	""", (item_code, sampai, company), as_dict=True)
	# Gudang tanpa Unit ikut, bukan dibuang: gudang transit disetel per company
	# dan lazimnya tidak berunit. Kalau dibuang, barang yang menginap di transit
	# tidak ikut dinilai ulang dan harga pokoknya waktu invoice memakai rate lama.
	return [
		(row.gudang, row.unit)
		for row in rows
		if not unit or not row.unit or row.unit == unit
	]


def get_gudang_transit(company, item_codes):
	"""Pasangan item dan gudang transit, untuk item yang memang ikut alur transit.

	Barang yang sudah keluar lewat Delivery Note tapi belum ditagih menumpuk di
	gudang transit; secara harga pokok dia masih persediaan sampai Sales Invoice
	terbit, jadi saldonya ikut Opening dan Closing. Mutasinya sengaja tidak
	ikut dihitung supaya penerimaan transit tidak terbaca sebagai produksi.
	"""
	from sth.mill.gudang_transit import get_item_transit, get_setelan_transit

	setelan = get_setelan_transit(company)
	if not setelan.warehouse:
		return []

	transit = get_item_transit(company)
	return [(item_code, setelan.warehouse) for item_code in item_codes if item_code in transit]


def get_sumber_stok(item_codes, company, unit=None):
	"""Pasangan item dan gudangnya. Gudang diambil dari Default Warehouse pada
	Item Defaults baris company ini. Kalau Unit diisi, gudang milik unit lain
	dibuang — diam-diam memakai gudang unit lain bikin angkanya kelihatan
	wajar padahal salah unit."""
	pasangan = []
	for item_code in item_codes:
		gudang = frappe.db.get_value(
			"Item Default",
			{"parent": item_code, "parenttype": "Item", "company": company},
			"default_warehouse",
		)
		if not gudang:
			continue
		if unit and frappe.db.get_value("Warehouse", gudang, "unit") != unit:
			continue
		pasangan.append((item_code, gudang))
	return pasangan


# ---------------------------------------------------------------------------
# Pengambilan data
# ---------------------------------------------------------------------------

def saldo_sle(item_code, warehouse, sampai):
	row = frappe.db.sql("""
		select qty_after_transaction, stock_value
		from `tabStock Ledger Entry`
		where item_code = %s and warehouse = %s and posting_date <= %s and is_cancelled = 0
		order by posting_date desc, posting_time desc, creation desc
		limit 1
	""", (item_code, warehouse, sampai), as_dict=True)
	if not row:
		return 0.0, 0.0
	return flt(row[0].qty_after_transaction), flt(row[0].stock_value)


def mutasi_sle(item_code, warehouse, dari, sampai):
	"""Mutasi periode dipecah per jenis voucher dan arah, supaya pembelian,
	produksi, penjualan, dan stock adjustment bisa dibedakan.

	Yang masih dipakai cuma 'pembelian_qty' dan 'pembelian_nilai' untuk baris
	Purchase ketiga produk. Production, Closing, dan Stock Adjustment sekarang
	diambil dari dokumen sumber di SUMBER_PRODUK, karena Stock Entry bikinan
	dokumen-dokumen itu cuma memposting selisih, bukan posisi. Bucket sisanya
	dibiarkan supaya pemisahan voucher-nya tetap terbaca kalau nanti diperlukan
	lagi."""
	rows = frappe.db.sql("""
		select
			voucher_type,
			case when actual_qty > 0 then 1 else -1 end as arah,
			sum(actual_qty) as qty,
			sum(stock_value_difference) as nilai
		from `tabStock Ledger Entry`
		where item_code = %s and warehouse = %s
			and posting_date between %s and %s and is_cancelled = 0
		group by voucher_type, arah
	""", (item_code, warehouse, dari, sampai), as_dict=True)

	hasil = {
		"pembelian_qty": 0.0, "pembelian_nilai": 0.0,
		"produksi_qty": 0.0,
		"penjualan_qty": 0.0,
		"adjustment_qty": 0.0,
	}

	for row in rows:
		qty = flt(row.qty)
		if row.voucher_type == VOUCHER_ADJUSTMENT:
			hasil["adjustment_qty"] += qty
		elif row.arah > 0 and row.voucher_type in VOUCHER_PEMBELIAN:
			hasil["pembelian_qty"] += qty
			hasil["pembelian_nilai"] += flt(row.nilai)
		elif row.arah > 0:
			hasil["produksi_qty"] += qty
		elif row.voucher_type in VOUCHER_PENJUALAN:
			hasil["penjualan_qty"] += abs(qty)

	return hasil


def _sumber(prefiks, field=None):
	"""Konfigurasi dokumen sumber satu produk, sekalian memastikan nama field yang
	diminta memang terdaftar. Nama doctype dan field masuk langsung ke SQL, jadi
	satu-satunya yang boleh lewat adalah yang tertulis di SUMBER_PRODUK."""
	cfg = SUMBER_PRODUK.get(prefiks)
	if not cfg:
		frappe.throw("Produk '{0}' tidak punya dokumen sumber.".format(prefiks))
	if field is not None and field not in (cfg["produksi"], cfg["closing"]):
		frappe.throw(
			"Field '{0}' tidak terdaftar sebagai sumber {1}.".format(field, cfg["doctype"])
		)
	return cfg


def _syarat_unit(unit, nilai):
	"""Company disaring lewat Unit, bukan lewat field company dokumen sumber:
	di Data TBS field itu tidak punya default maupun fetch_from dan lazimnya
	kosong, jadi menyaringnya membuang semua barisnya."""
	if not unit:
		return ""
	nilai["unit"] = unit
	return "and d.unit = %(unit)s"


def sumber_terakhir(prefiks, field, company, unit, dari, sampai):
	"""Isi satu field pada dokumen sumber terakhir dalam rentang tanggal.

	Dipakai Closing ketiga produk dan Production TBS. Angka posisi, bukan jumlah.

	Tanpa Unit, tiap unit diambil dokumen terakhirnya sendiri lalu dijumlahkan.
	Kalau dicari satu dokumen terakhir untuk seluruh company, unit yang berhenti
	produksi lebih dulu hilang gara-gara unit lain punya dokumen yang lebih baru."""
	cfg = _sumber(prefiks, field)
	daftar_unit = [unit] if unit else frappe.get_all("Unit", filters={"company": company}, pluck="name")

	total = 0.0
	for nama_unit in daftar_unit:
		row = frappe.db.sql("""
			select `{field}`
			from `tab{doctype}`
			where docstatus = 1 and unit = %(unit)s
				and `{tanggal}` between %(dari)s and %(sampai)s
			order by `{tanggal}` desc, creation desc
			limit 1
		""".format(field=field, doctype=cfg["doctype"], tanggal=cfg["tanggal"]),
			{"unit": nama_unit, "dari": dari, "sampai": sampai})
		if row:
			total += flt(row[0][0])

	return total


def sumber_total(prefiks, field, company, unit, dari, sampai):
	"""Jumlah satu field pada seluruh dokumen sumber dalam rentang tanggal.
	Dipakai Production CPO dan PK, yang mencatat pengiriman per hari."""
	cfg = _sumber(prefiks, field)
	nilai = {"company": company, "dari": dari, "sampai": sampai}
	syarat = _syarat_unit(unit, nilai)

	row = frappe.db.sql("""
		select sum(d.`{field}`)
		from `tab{doctype}` d
		inner join `tabUnit` u on u.name = d.unit
		where d.docstatus = 1 and u.company = %(company)s
			and d.`{tanggal}` between %(dari)s and %(sampai)s
			{syarat}
	""".format(field=field, doctype=cfg["doctype"], tanggal=cfg["tanggal"], syarat=syarat), nilai)

	return flt(row[0][0]) if row and row[0] else 0.0


def ada_dokumen_sumber(prefiks, company, unit, dari, sampai):
	"""Membedakan 'memang tidak ada produksi' dari 'dokumennya belum disubmit';
	tanpa ini Production nol lewat tanpa peringatan."""
	cfg = _sumber(prefiks)
	nilai = {"company": company, "dari": dari, "sampai": sampai}
	syarat = _syarat_unit(unit, nilai)

	return bool(frappe.db.sql("""
		select d.name
		from `tab{doctype}` d
		inner join `tabUnit` u on u.name = d.unit
		where d.docstatus = 1 and u.company = %(company)s
			and d.`{tanggal}` between %(dari)s and %(sampai)s
			{syarat}
		limit 1
	""".format(doctype=cfg["doctype"], tanggal=cfg["tanggal"], syarat=syarat), nilai))


def rate_dari_stock_entry(prefiks, produk, company, unit, dari, sampai):
	"""Basic Rate produk pada Stock Entry bikinan dokumen sumber terakhir.

	Ketiga dokumen sumber menempelkan namanya di field references Stock Entry,
	jadi rate yang dipakai ERPNext memvaluasi produk itu bisa dibaca balik.
	Sengaja tidak disimpan di field dokumen supaya tidak bisa diketik ulang di
	form: nilainya harus selalu sama dengan yang dipakai Stock Ledger.

	Yang dicari dokumen terakhir yang punya Stock Entry, bukan dokumen terakhir
	lalu menyerah kalau kosong: ketiganya cuma membuat Stock Entry kalau ada
	produksi, jadi hari terakhir bisa saja tidak punya.

	Satu rate untuk semua unit. Kalau unit-unitnya punya rate yang berbeda jauh,
	isi Unit di dokumen ini supaya tiap unit dihitung sendiri."""
	cfg = _sumber(prefiks)
	nilai = {
		"company": company,
		"dari": dari,
		"sampai": sampai,
		"doctype": cfg["doctype"],
		"tipe": TIPE_BARANG[produk],
	}
	syarat = _syarat_unit(unit, nilai)

	row = frappe.db.sql("""
		select sed.basic_rate, sed.valuation_rate
		from `tabStock Entry Detail` sed
		inner join `tabStock Entry` se on se.name = sed.parent
		inner join `tab{doctype}` d on d.name = se.references
		inner join `tabUnit` u on u.name = d.unit
		inner join `tabItem` i on i.name = sed.item_code
		where se.docstatus = 1 and se.reference_doctype = %(doctype)s
			and d.docstatus = 1 and u.company = %(company)s
			and i.tipe_barang = %(tipe)s
			and d.`{tanggal}` between %(dari)s and %(sampai)s
			{syarat}
		order by d.`{tanggal}` desc, d.creation desc, sed.idx desc
		limit 1
	""".format(doctype=cfg["doctype"], tanggal=cfg["tanggal"], syarat=syarat), nilai, as_dict=True)

	if not row:
		return 0.0
	return flt(row[0].basic_rate) or flt(row[0].valuation_rate)


def total_biaya(company, kelompok, dari, sampai):
	akun_induk = get_sumber_biaya(company, kelompok)
	if not akun_induk:
		return 0.0

	akun = set()
	for nama in akun_induk:
		batas = frappe.db.get_value("Account", nama, ["lft", "rgt"])
		if not batas:
			continue
		lft, rgt = batas
		akun.update(frappe.get_all(
			"Account",
			filters={
				"company": company,
				"is_group": 0,
				"lft": (">=", lft),
				"rgt": ("<=", rgt),
			},
			pluck="name",
		))

	if not akun:
		return 0.0

	total = frappe.db.sql("""
		select sum(debit) - sum(credit)
		from `tabGL Entry`
		where company = %s and posting_date between %s and %s
			and is_cancelled = 0 and account in %s
	""", (company, dari, sampai, tuple(akun)))

	return flt(total[0][0]) if total else 0.0


def saldo_akun(company, akun, sampai):
	if not akun:
		return 0.0
	total = frappe.db.sql("""
		select sum(debit) - sum(credit)
		from `tabGL Entry`
		where company = %s and account = %s and posting_date <= %s and is_cancelled = 0
	""", (company, akun, sampai))
	return flt(total[0][0]) if total else 0.0


def harga_rata_jual(company, item_codes, dari, sampai):
	if not item_codes:
		return 0.0
	row = frappe.db.sql("""
		select sum(sii.base_net_amount) as nilai, sum(sii.qty) as qty
		from `tabSales Invoice Item` sii
		join `tabSales Invoice` si on si.name = sii.parent
		where si.docstatus = 1 and si.is_return = 0 and si.company = %s
			and si.posting_date between %s and %s and sii.item_code in %s
	""", (company, dari, sampai, tuple(item_codes)), as_dict=True)
	if not row or not flt(row[0].qty):
		return 0.0
	return flt(row[0].nilai) / flt(row[0].qty)


def ambil_data(periode_dari, periode_sampai, company, unit=None):
	"""Kumpulkan angka dari dokumen sumber. Tidak lagi diekspos ke klien: yang
	dipanggil tombol Ambil Data adalah method dokumen dengan nama sama, supaya
	baris turunannya ikut terhitung."""
	setelan = get_setelan(company)

	nilai = {}
	peringatan = []

	for produk, prefiks in PREFIKS.items():
		item_codes = get_item_produk(produk)
		if not item_codes:
			peringatan.append(
				"{0}: belum ada Item dengan Tipe Barang '{1}'.".format(produk, TIPE_BARANG[produk])
			)
			continue

		pasangan = get_sumber_stok(item_codes, company, unit)
		if not pasangan:
			peringatan.append(
				"{0}: Item dengan Tipe Barang '{1}' belum punya Default Warehouse "
				"di Item Defaults untuk company {2}{3}.".format(
					produk,
					TIPE_BARANG[produk],
					company,
					" unit {0}".format(unit) if unit else "",
				)
			)
			continue

		# Satu produk bisa tersebar di beberapa item/gudang, jadi saldo dan
		# mutasinya dijumlahkan dulu sebelum masuk ke baris rincian.
		opening_qty = opening_nilai = 0.0
		mutasi = {
			"pembelian_qty": 0.0, "pembelian_nilai": 0.0,
			"produksi_qty": 0.0,
			"penjualan_qty": 0.0,
			"adjustment_qty": 0.0,
		}
		for item_code, gudang in pasangan:
			for kunci, angka in mutasi_sle(item_code, gudang, periode_dari, periode_sampai).items():
				mutasi[kunci] += angka

		# Opening = sisa stok tiap item di gudang default-nya sehari sebelum
		# periode, bukan baris pemakaian dokumen COGS periode lalu. Gudang
		# transit ikut dijumlahkan karena barang yang sudah keluar lewat
		# Delivery Note tapi belum ditagih secara harga pokok masih persediaan;
		# mutasinya sengaja tidak ikut supaya penerimaan transit tidak terbaca
		# sebagai produksi.
		pasangan_saldo = pasangan + get_gudang_transit(
			company, [item_code for item_code, _gudang in pasangan]
		)
		for item_code, gudang in pasangan_saldo:
			qty_awal, nilai_awal = saldo_sle(item_code, gudang, add_days(periode_dari, -1))
			opening_qty += qty_awal
			opening_nilai += nilai_awal

		nilai[prefiks + "_opening"] = (opening_qty, opening_nilai)
		nilai[prefiks + "_purchase"] = (mutasi["pembelian_qty"], mutasi["pembelian_nilai"])
		# Production dan Closing ketiganya dari dokumen sumber, bukan mutasi
		# Stock Ledger. Closing dinegatifkan karena rantai di hitung()
		# menjumlahkan, tidak mengurangkan.
		cfg = SUMBER_PRODUK[prefiks]
		hitung_produksi = sumber_total if cfg["produksi_total"] else sumber_terakhir
		nilai[prefiks + "_production"] = (
			hitung_produksi(prefiks, cfg["produksi"], company, unit, periode_dari, periode_sampai),
			0,
		)
		nilai[prefiks + "_closing"] = (
			-sumber_terakhir(prefiks, cfg["closing"], company, unit, periode_dari, periode_sampai),
			0,
		)
		if not ada_dokumen_sumber(prefiks, company, unit, periode_dari, periode_sampai):
			peringatan.append(
				"{0}: belum ada {1} yang disubmit untuk {2} sampai {3} di company "
				"{4}{5}, jadi Production dan Closing Stock-nya nol.".format(
					produk,
					cfg["doctype"],
					periode_dari,
					periode_sampai,
					company,
					" unit {0}".format(unit) if unit else "",
				)
			)

		if prefiks == "tbs":
			# Penjualan TBS ke pihak ketiga dinolkan dulu atas permintaan user;
			# qty-nya masih bisa diisi manual di grid dan tetap ikut dihitung.
			nilai["tbs_sold"] = (0, 0)
		else:
			# Stock Adjustment juga dinolkan dulu; mutasi Stock Reconciliation
			# tetap dihitung di mutasi_sle kalau nanti mau dipakai lagi.
			nilai[prefiks + "_adjustment"] = (0, 0)

	rincian = []
	for kode, produk, label in BARIS:
		qty, amount = nilai.get(kode, (0, 0))
		rincian.append({
			"kode": kode,
			"produk": produk,
			"baris": label,
			"qty": flt(qty),
			"amount": flt(amount, 2),
			"rate": (flt(amount) / flt(qty)) if flt(qty) else 0,
		})

	return {
		"rincian": rincian,
		"biaya_kebun": total_biaya(company, "Kebun", periode_dari, periode_sampai),
		"biaya_mill": total_biaya(company, "Mill", periode_dari, periode_sampai),
		"harga_rata_cpo": harga_rata_jual(company, get_item_produk("CPO"), periode_dari, periode_sampai),
		"harga_rata_pk": harga_rata_jual(company, get_item_produk("Palm Kernel"), periode_dari, periode_sampai),
		"saldo_gl_tbs": saldo_akun(company, setelan and setelan.akun_persediaan_tbs, periode_sampai),
		"saldo_gl_cpo": saldo_akun(company, setelan and setelan.akun_persediaan_cpo, periode_sampai),
		"saldo_gl_pk": saldo_akun(company, setelan and setelan.akun_persediaan_pk, periode_sampai),
		"peringatan": peringatan,
	}
