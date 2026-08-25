# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import erpnext
import frappe
from erpnext.accounts.general_ledger import make_gl_entries, make_reverse_gl_entries
from frappe.model.document import Document
from frappe.utils import add_days, flt

# Produk dikenali lewat Item.tipe_barang dan Warehouse.warehouse_category,
# sama seperti Data TBS dan Sounding Stock CPO/Palm Kernel.
TIPE_BARANG = {"TBS": "TBS", "CPO": "CPO", "Palm Kernel": "Palm Kernel"}
KATEGORI_GUDANG = {
	"TBS": "TBS",
	"CPO": "Product CPO",
	"Palm Kernel": "Product Palm Kernel",
}

PREFIKS = {"TBS": "tbs", "CPO": "cpo", "Palm Kernel": "pk"}

VOUCHER_PEMBELIAN = ("Purchase Receipt", "Purchase Invoice")
VOUCHER_PENJUALAN = ("Delivery Note", "Sales Invoice")
VOUCHER_ADJUSTMENT = "Stock Reconciliation"

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

KETERANGAN_KEBUN = "KAPITALISASI BIAYA KEBUN KE PERSEDIAAN TBS"
KETERANGAN_OLAH = "PENGOLAHAN TBS MENJADI CPO DAN PALM KERNEL"
KETERANGAN_HPP = "HARGA POKOK PENJUALAN {0}"


class COGSMilldanKebun(Document):

	def validate(self):
		self.validasi_periode()
		self.hitung()

	def on_submit(self):
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

	# ------------------------------------------------------------------
	# Perhitungan
	# ------------------------------------------------------------------

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

		# --- TBS: biaya kebun jadi nilai produksi, sisanya rata-rata tertimbang
		isi("tbs_production", amount=flt(self.biaya_kebun))
		isi(
			"tbs_available",
			qty=q("tbs_opening") + q("tbs_production") + q("tbs_purchase"),
			amount=a("tbs_opening") + a("tbs_production") + a("tbs_purchase"),
		)
		rate_tbs = a("tbs_available") / q("tbs_available") if q("tbs_available") else 0
		# Qty Closing dan Sold disimpan positif lalu dikurangkan di sini; di
		# excel keduanya ditulis negatif lalu dijumlahkan.
		isi("tbs_closing", amount=rate_tbs * q("tbs_closing"))
		isi(
			"tbs_cop",
			qty=q("tbs_available") - q("tbs_closing"),
			amount=a("tbs_available") - a("tbs_closing"),
		)
		isi("tbs_sold", amount=rate_tbs * q("tbs_sold"))
		isi(
			"tbs_internal",
			qty=q("tbs_cop") - q("tbs_sold"),
			amount=a("tbs_cop") - a("tbs_sold"),
		)

		# --- Conversion cost: OER dan KER dari qty produksi terhadap TBS diolah
		self.qty_tbs_diolah = q("tbs_internal")
		self.oer = (q("cpo_production") / self.qty_tbs_diolah * 100) if self.qty_tbs_diolah else 0
		self.ker = (q("pk_production") / self.qty_tbs_diolah * 100) if self.qty_tbs_diolah else 0

		nilai_cpo = flt(self.oer) * flt(self.harga_rata_cpo)
		nilai_pk = flt(self.ker) * flt(self.harga_rata_pk)
		pembagi = nilai_cpo + nilai_pk

		self.conversion_cost_cpo = (nilai_cpo / pembagi * 100) if pembagi else 0
		self.conversion_cost_pk = (100 - flt(self.conversion_cost_cpo)) if pembagi else 0

		# --- Biaya yang dibagi ke CPO dan PK: TBS diolah ditambah biaya mill
		nilai_tbs_diolah = flt(a("tbs_internal"), 2)
		nilai_mill = flt(self.biaya_mill, 2)
		dibagi = nilai_tbs_diolah + nilai_mill

		if dibagi and not pembagi:
			frappe.throw(
				"Average Price CPO dan PK belum terisi, conversion cost tidak bisa dihitung "
				"sehingga biaya TBS dan biaya mill tidak punya tujuan alokasi."
			)

		amount_cpo = flt(dibagi * flt(self.conversion_cost_cpo) / 100, 2)
		isi("cpo_production", amount=amount_cpo)
		isi("pk_production", amount=dibagi - amount_cpo)

		# --- CPO dan PK: rata-rata tertimbang, stock adjustment hanya qty
		for prefiks in ("cpo", "pk"):
			isi(
				prefiks + "_available",
				qty=q(prefiks + "_opening") + q(prefiks + "_purchase") + q(prefiks + "_production"),
				amount=a(prefiks + "_opening") + a(prefiks + "_purchase") + a(prefiks + "_production"),
			)
			rate = (
				a(prefiks + "_available") / q(prefiks + "_available")
				if q(prefiks + "_available")
				else 0
			)
			# Selisih nilai stock adjustment sengaja tidak dijurnal, mengikuti
			# excel: qty-nya menambah COGS, nilainya terserap lewat rate.
			isi(prefiks + "_adjustment", amount=0)
			isi(prefiks + "_closing", amount=rate * q(prefiks + "_closing"))
			isi(
				prefiks + "_cogs",
				qty=q(prefiks + "_available") + q(prefiks + "_adjustment") - q(prefiks + "_closing"),
				amount=a(prefiks + "_available") - a(prefiks + "_closing"),
			)

		self.tulis_rincian(nilai)
		self.susun_closing(nilai)
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

		self.selisih_gl_tbs = flt(
			flt(self.saldo_gl_tbs)
			+ a("tbs_production")
			- a("tbs_internal")
			- a("tbs_sold")
			- a("tbs_closing"),
			2,
		)
		for prefiks in ("cpo", "pk"):
			self.set(
				"selisih_gl_" + prefiks,
				flt(
					flt(self.get("saldo_gl_" + prefiks))
					+ a(prefiks + "_production")
					- a(prefiks + "_cogs")
					- a(prefiks + "_closing"),
					2,
				),
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

		self.total_closing = sum(flt(row["debit"]) for row in baris)

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
	return frappe.db.get_value("Item", {"tipe_barang": TIPE_BARANG[produk]}, "name")


def get_gudang_produk(produk, company, unit=None):
	"""Gudang selalu disaring per company. Kalau Unit diisi tapi tidak punya
	gudang produk, jangan jatuh ke gudang company — unit kebun tidak punya
	gudang TBS/CPO/PK, dan diam-diam memakai gudang mill bikin angkanya
	kelihatan wajar padahal salah unit."""
	filters = {
		"warehouse_category": KATEGORI_GUDANG[produk],
		"is_group": 0,
		"company": company,
	}
	if unit:
		filters["unit"] = unit
	return frappe.db.get_value("Warehouse", filters, "name")


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
	produksi, penjualan, dan stock adjustment bisa dibedakan."""
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


def opening_dari_dokumen_sebelumnya(company, unit, periode_dari):
	"""Opening diambil dari Closing Stock dokumen periode sebelumnya supaya
	rantai nilainya nyambung; kalau belum ada, jatuh ke Stock Ledger."""
	filters = {
		"company": company,
		"docstatus": 1,
		"periode_sampai": ("<", periode_dari),
	}
	if unit:
		filters["unit"] = unit

	nama = frappe.db.get_value(
		"COGS Mill dan Kebun", filters, "name", order_by="periode_sampai desc"
	)
	if not nama:
		return {}

	akhiran = "_closing"
	hasil = {}
	for row in frappe.get_all(
		"COGS Mill dan Kebun Rincian",
		filters={"parent": nama, "parenttype": "COGS Mill dan Kebun"},
		fields=["kode", "qty", "amount"],
	):
		if row.kode and row.kode.endswith(akhiran):
			hasil[row.kode[: -len(akhiran)]] = (flt(row.qty), flt(row.amount))
	return hasil


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


def harga_rata_jual(company, item_code, dari, sampai):
	if not item_code:
		return 0.0
	row = frappe.db.sql("""
		select sum(sii.base_net_amount) as nilai, sum(sii.qty) as qty
		from `tabSales Invoice Item` sii
		join `tabSales Invoice` si on si.name = sii.parent
		where si.docstatus = 1 and si.is_return = 0 and si.company = %s
			and si.posting_date between %s and %s and sii.item_code = %s
	""", (company, dari, sampai, item_code), as_dict=True)
	if not row or not flt(row[0].qty):
		return 0.0
	return flt(row[0].nilai) / flt(row[0].qty)


@frappe.whitelist()
def ambil_data(periode_dari, periode_sampai, company, unit=None):
	setelan = get_setelan(company)
	sebelumnya = opening_dari_dokumen_sebelumnya(company, unit, periode_dari)

	nilai = {}
	peringatan = []

	for produk, prefiks in PREFIKS.items():
		item_code = get_item_produk(produk)
		gudang = get_gudang_produk(produk, company, unit)

		if not item_code:
			peringatan.append(
				"{0}: belum ada Item dengan Tipe Barang '{1}'.".format(produk, TIPE_BARANG[produk])
			)
			continue
		if not gudang:
			peringatan.append(
				"{0}: belum ada Warehouse dengan Warehouse Category '{1}'.".format(
					produk, KATEGORI_GUDANG[produk]
				)
			)
			continue

		if prefiks in sebelumnya:
			opening_qty, opening_nilai = sebelumnya[prefiks]
		else:
			opening_qty, opening_nilai = saldo_sle(item_code, gudang, add_days(periode_dari, -1))

		mutasi = mutasi_sle(item_code, gudang, periode_dari, periode_sampai)
		closing_qty, _closing_nilai = saldo_sle(item_code, gudang, periode_sampai)

		nilai[prefiks + "_opening"] = (opening_qty, opening_nilai)
		nilai[prefiks + "_purchase"] = (mutasi["pembelian_qty"], mutasi["pembelian_nilai"])
		nilai[prefiks + "_production"] = (mutasi["produksi_qty"], 0)
		nilai[prefiks + "_closing"] = (closing_qty, 0)
		if prefiks == "tbs":
			nilai["tbs_sold"] = (mutasi["penjualan_qty"], 0)
		else:
			nilai[prefiks + "_adjustment"] = (mutasi["adjustment_qty"], 0)

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
