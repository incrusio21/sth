# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, cstr, flt, getdate

from sth.plantation.doctype.blok.blok import BULAN_MAP
from sth.accounting_sth.doctype.master_harga_shu.master_harga_shu import get_harga_shu, masa_setahun

# Semua uang dibulatkan dengan aturan yang sama. Excel lama membulatkan Management
# Fee ke rupiah penuh tapi PPh 22 tidak — perbedaannya tidak punya alasan, jadi
# tidak ditiru. Akibatnya angka bisa meleset ~0,2 rupiah dari Excel lama.
PRESISI_UANG = 2
PRESISI_BERAT = 3


def normalisasi_tahun_tanam(nilai):
	"""`Blok.tahun_tanam` bertipe Data, jadi "2010" dan "2010 " bisa hidup berdampingan.

	Tanpa normalisasi keduanya jadi dua kelompok berbeda saat dijumlahkan, dan
	yang tidak cocok dengan Master Harga SHU mengembalikan harga 0 tanpa suara.
	"""
	return cint(cstr(nilai).strip())


def pecah_berat_baris(row):
	"""Pecah berat satu baris SPB antara blok dan blok_restan. Fungsi murni.

	`total_weight` dialokasikan ke baris, bukan ke blok — padahal satu baris bisa
	memuat dua blok dengan tahun tanam berbeda (`blok` dan `blok_restan`).
	Pembagiannya mengikuti janjang, dan blok utama menyerap sisa pembulatan
	supaya jumlah kedua pecahan selalu persis sama dengan berat barisnya.

	Balikan: list of (tahun_tanam, berat).
	"""
	berat = flt(row.get("total_weight"))
	if not berat:
		return []

	tt_utama = normalisasi_tahun_tanam(row.get("tahun_tanam"))
	qty_restan = flt(row.get("qty_restan"))

	if not row.get("blok_restan") or qty_restan <= 0:
		return [(tt_utama, berat)]

	tt_restan = normalisasi_tahun_tanam(row.get("tahun_tanam_restan"))
	if tt_restan == tt_utama:
		# Tahun tanamnya sama — dipecah pun akan digabung lagi, dan pemecahan
		# hanya menambah kesempatan salah bulat.
		return [(tt_utama, berat)]

	total_janjang = flt(row.get("total_janjang")) or (flt(row.get("qty")) + qty_restan)
	if total_janjang <= 0:
		return [(tt_utama, berat)]

	berat_restan = flt(berat * qty_restan / total_janjang, PRESISI_BERAT)
	berat_utama = flt(berat - berat_restan, PRESISI_BERAT)

	return [(tt_utama, berat_utama), (tt_restan, berat_restan)]


def cari_masa(masa_rows, tanggal):
	"""Masa yang memuat tanggal itu, atau None. Fungsi murni."""
	tanggal = getdate(tanggal)

	for masa in masa_rows:
		if getdate(masa["tanggal_mulai"]) <= tanggal <= getdate(masa["tanggal_selesai"]):
			return masa

	return None


def kelompokkan_netto(baris_spb, masa_rows):
	"""Kelompokkan netto SPB per (masa, tahun tanam). Fungsi murni — tanpa database.

	Balikan: (hasil, terlewat). `hasil` urut menurut masa lalu tahun tanam.
	`terlewat` berisi baris yang tanggalnya tidak masuk masa manapun — seharusnya
	kosong, karena Masa SHU wajib menutup satu bulan penuh.
	"""
	ember = {}
	terlewat = []

	for row in baris_spb:
		masa = cari_masa(masa_rows, row.get("posting_date"))
		if not masa:
			terlewat.append(row)
			continue

		for tahun_tanam, berat in pecah_berat_baris(row):
			kunci = (cint(masa["masa_no"]), tahun_tanam)
			if kunci not in ember:
				ember[kunci] = {
					"masa_shu": masa.get("masa_shu"),
					"masa_no": cint(masa["masa_no"]),
					"tanggal_mulai": masa["tanggal_mulai"],
					"tanggal_selesai": masa["tanggal_selesai"],
					"tahun_tanam": tahun_tanam,
					"netto_kg": 0.0,
				}
			ember[kunci]["netto_kg"] += berat

	hasil = []
	for kunci in sorted(ember):
		baris = ember[kunci]
		baris["netto_kg"] = flt(baris["netto_kg"], PRESISI_BERAT)
		hasil.append(baris)

	return hasil, terlewat


def hitung_shu(
	jumlah_produksi,
	biaya_perawatan,
	persen_management_fee,
	persen_pph22,
	persen_bagi_hasil,
):
	"""Rangkaian potongan sampai pembagian. Fungsi murni — tanpa database.

	Management Fee dan PPh 22 sama-sama dihitung dari Jumlah Produksi TBS, bukan
	dari angka setelah potongan. Tata letak sheet Excel mudah membuat keliru.
	"""
	jumlah_produksi = flt(jumlah_produksi, PRESISI_UANG)
	biaya_perawatan = flt(biaya_perawatan, PRESISI_UANG)

	management_fee = flt(jumlah_produksi * flt(persen_management_fee) / 100, PRESISI_UANG)
	jumlah_biaya_operasional = flt(biaya_perawatan + management_fee, PRESISI_UANG)
	setelah_biaya_operasional = flt(jumlah_produksi - jumlah_biaya_operasional, PRESISI_UANG)

	pph22 = flt(jumlah_produksi * flt(persen_pph22) / 100, PRESISI_UANG)
	hasil_bersih = flt(setelah_biaya_operasional - pph22, PRESISI_UANG)

	angsuran_hutang = flt(hasil_bersih * flt(persen_bagi_hasil) / 100, PRESISI_UANG)
	# Sisa, bukan hitung ulang — supaya kedua bagian selalu berjumlah persis
	# Hasil Bersih walaupun persentasenya bukan 50.
	pembayaran_ke_mitra = flt(hasil_bersih - angsuran_hutang, PRESISI_UANG)

	return {
		"management_fee": management_fee,
		"jumlah_biaya_operasional": jumlah_biaya_operasional,
		"setelah_biaya_operasional": setelah_biaya_operasional,
		"pph22": pph22,
		"hasil_bersih": hasil_bersih,
		"angsuran_hutang": angsuran_hutang,
		"pembayaran_ke_mitra": pembayaran_ke_mitra,
	}


def ambil_baris_spb(company, units, tanggal_mulai, tanggal_selesai):
	"""Baris SPB mentah dalam rentang tanggal, belum dipecah dan belum dikelompokkan.

	Pengelompokan sengaja tidak dilakukan di SQL: berat satu baris bisa jatuh ke
	dua tahun tanam sekaligus, dan pemecahannya harus bisa dites tanpa database.
	"""
	if not units:
		return []

	return frappe.db.sql(
		"""
		SELECT s.name AS spb, s.posting_date,
		       d.qty, d.qty_restan, d.total_janjang, d.total_weight,
		       d.blok, d.blok_restan,
		       b.tahun_tanam AS tahun_tanam,
		       br.tahun_tanam AS tahun_tanam_restan
		FROM `tabSPB Timbangan Pabrik` d
		INNER JOIN `tabSurat Pengantar Buah` s ON d.parent = s.name
		INNER JOIN `tabUnit` u ON s.unit = u.name
		LEFT JOIN `tabBlok` b ON d.blok = b.name
		LEFT JOIN `tabBlok` br ON d.blok_restan = br.name
		WHERE s.docstatus = 1
		  AND s.company = %(company)s
		  AND u.plasma = 1
		  AND s.unit IN %(units)s
		  AND s.posting_date BETWEEN %(tanggal_mulai)s AND %(tanggal_selesai)s
		ORDER BY s.posting_date, s.name
		""",
		{
			"company": company,
			"units": tuple(units),
			"tanggal_mulai": getdate(tanggal_mulai),
			"tanggal_selesai": getdate(tanggal_selesai),
		},
		as_dict=True,
	)


class PerhitunganKUD(Document):
	def autoname(self):
		abbr = frappe.get_cached_value("Company", self.company, "abbr")
		bulan_no = BULAN_MAP.get(self.bulan)
		if not bulan_no:
			frappe.throw(_("Bulan tidak dikenali: {0}").format(self.bulan))

		self.name = f"PK-{abbr}-{cint(self.tahun):04d}-{bulan_no:02d}-{self.mitra}"

	def validate(self):
		self.set_periode()
		self.validate_unit()
		self.validate_duplikat()
		self.hitung_baris()
		self.hitung_rekap()
		self.set_status_harga()

	def on_submit(self):
		self.validate_semua_baris_berharga()

	def masa_bulan_ini(self):
		"""Masa bulan ini dari Masa SHU. Rentang tanggal tidak pernah dihitung sendiri."""
		bulan_no = BULAN_MAP.get(self.bulan)
		return [m for m in masa_setahun(self.company, self.tahun) if cint(m.bulan_no) == cint(bulan_no)]

	def set_periode(self):
		self.bulan_no = BULAN_MAP.get(self.bulan)
		if not self.bulan_no:
			frappe.throw(_("Bulan tidak dikenali: {0}").format(self.bulan))

		masa_rows = self.masa_bulan_ini()
		if not masa_rows:
			frappe.throw(
				_(
					"Masa SHU {0} {1} untuk {2} belum ada atau belum disubmit. "
					"Buat dan submit dulu di sana — rentang tanggal perhitungan ini diambil dari situ."
				).format(self.bulan, self.tahun, self.company),
				title=_("Masa SHU Belum Ada"),
			)

		self.tanggal_mulai = min(getdate(m.tanggal_mulai) for m in masa_rows)
		self.tanggal_selesai = max(getdate(m.tanggal_selesai) for m in masa_rows)

	def validate_unit(self):
		if not self.unit:
			frappe.throw(_("Pilih minimal satu Unit plasma."), title=_("Unit Belum Diisi"))

		bukan_plasma = []
		salah_company = []

		for row in self.unit:
			company, plasma = frappe.get_cached_value("Unit", row.unit, ["company", "plasma"])
			if company != self.company:
				salah_company.append(row.unit)
			elif not plasma:
				bukan_plasma.append(row.unit)

		errors = []
		if salah_company:
			errors.append(
				_("Unit ini bukan milik {0}: {1}").format(self.company, ", ".join(salah_company))
			)
		if bukan_plasma:
			errors.append(_("Unit ini tidak ditandai plasma: {0}").format(", ".join(bukan_plasma)))

		if errors:
			frappe.throw("<br>".join(errors), title=_("Unit Belum Benar"))

	def validate_duplikat(self):
		lain = frappe.db.exists(
			"Perhitungan KUD",
			{
				"company": self.company,
				"mitra": self.mitra,
				"tahun": self.tahun,
				"bulan": self.bulan,
				"docstatus": 1,
				"name": ("!=", self.name),
			},
		)
		if lain:
			frappe.throw(
				_("Perhitungan KUD {0} {1} untuk {2} sudah ada dan sudah disubmit: {3}").format(
					self.bulan, self.tahun, self.mitra, lain
				)
			)

	def hitung_baris(self):
		for row in self.detail:
			row.netto_kg = flt(row.netto_kg, PRESISI_BERAT)
			row.total = flt(flt(row.netto_kg) * flt(row.harga), PRESISI_UANG)

	def hitung_rekap(self):
		self.total_netto = flt(sum(flt(row.netto_kg) for row in self.detail), PRESISI_BERAT)
		self.jumlah_produksi = flt(sum(flt(row.total) for row in self.detail), PRESISI_UANG)

		hasil = hitung_shu(
			self.jumlah_produksi,
			self.biaya_perawatan,
			self.persen_management_fee,
			self.persen_pph22,
			self.persen_bagi_hasil,
		)
		self.update(hasil)

	def baris_tanpa_harga(self):
		return [row for row in self.detail if flt(row.netto_kg) and not flt(row.harga)]

	def set_status_harga(self):
		if not self.detail:
			self.status_harga = _("Produksi belum ditarik")
			return

		kosong = self.baris_tanpa_harga()
		if kosong:
			self.status_harga = _("{0} dari {1} baris belum ada harganya").format(
				len(kosong), len(self.detail)
			)
		else:
			self.status_harga = _("{0} baris, semua sudah berharga").format(len(self.detail))

	def validate_semua_baris_berharga(self):
		"""Dokumen ini yang menentukan uang yang dibayar — tidak boleh disubmit
		dengan harga 0. `get_harga_shu()` memang sengaja mengembalikan 0 supaya
		transaksi boleh mendahului penetapan harga, tapi kelonggaran itu berhenti
		di sini: netto berharga 0 berarti mitra dibayar kurang tanpa jejak.
		"""
		kosong = self.baris_tanpa_harga()
		if not kosong:
			return

		daftar = ", ".join(
			_("Masa {0} tahun tanam {1}").format(row.masa_no, row.tahun_tanam) for row in kosong
		)
		frappe.throw(
			_(
				"Harga belum ditetapkan untuk: {0}. "
				"Tetapkan dulu di Master Harga SHU, lalu tarik ulang produksinya."
			).format(daftar),
			title=_("Masih Ada Netto Tanpa Harga"),
		)

	@frappe.whitelist()
	def tarik_produksi(self):
		"""Isi ulang detail dari SPB yang sudah disubmit. Tombol di form."""
		self.set_periode()
		self.validate_unit()

		masa_rows = self.masa_bulan_ini()
		baris_spb = ambil_baris_spb(
			self.company,
			[row.unit for row in self.unit],
			self.tanggal_mulai,
			self.tanggal_selesai,
		)
		netto, terlewat = kelompokkan_netto(baris_spb, masa_rows)

		self.set("detail", [])
		for baris in netto:
			self.append(
				"detail",
				{
					**baris,
					"harga": get_harga_shu(self.company, baris["tanggal_mulai"], baris["tahun_tanam"]),
				},
			)

		self.hitung_baris()
		self.hitung_rekap()
		self.set_status_harga()

		if terlewat:
			frappe.msgprint(
				_("{0} baris SPB tanggalnya tidak masuk masa manapun dan tidak ikut dihitung.").format(
					len(terlewat)
				),
				title=_("Ada SPB di Luar Masa"),
				indicator="orange",
			)

		tanpa_tahun_tanam = [row for row in self.detail if not cint(row.tahun_tanam)]
		if tanpa_tahun_tanam:
			frappe.msgprint(
				_("{0} baris blok-nya belum punya tahun tanam. Nettonya masuk kelompok 0 dan pasti tak berharga.").format(
					len(tanpa_tahun_tanam)
				),
				title=_("Ada Blok Tanpa Tahun Tanam"),
				indicator="orange",
			)

		return {"jumlah_baris": len(self.detail), "status_harga": self.status_harga}


@frappe.whitelist()
def get_unit_plasma(company):
	"""Semua unit plasma milik company. Dipakai untuk mengisi awal daftar unit."""
	return frappe.get_all(
		"Unit",
		filters={"company": company, "plasma": 1},
		pluck="name",
		order_by="name",
	)
