# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate

from sth.plantation.doctype.blok.blok import BULAN_MAP
from sth.accounting_sth.doctype.master_harga_shu.master_harga_shu import (
	get_harga_shu,
	masa_setahun,
	normalisasi_tahun_tanam,
)

# Semua uang dibulatkan dengan aturan yang sama. Excel lama membulatkan Management
# Fee ke rupiah penuh tapi PPh 22 tidak — perbedaannya tidak punya alasan, jadi
# tidak ditiru. Akibatnya angka bisa meleset ~0,2 rupiah dari Excel lama.
PRESISI_UANG = 2
PRESISI_BERAT = 3

# Biaya yang ditanggung mitra, per jenis Buku Kerja Mandor. Ketiganya persis
# bagian-bagian label "Biaya Perawatan, Panen & Transport": traksi yang jadi
# transportnya.
BKM_BIAYA = (
	("Buku Kerja Mandor Perawatan", "biaya_bkm_perawatan"),
	("Buku Kerja Mandor Panen", "biaya_bkm_panen"),
	("Buku Kerja Mandor Traksi", "biaya_bkm_traksi"),
)


def pecah_netto_tiket(rows):
	"""Bagi netto satu tiket timbangan ke tahun tanam baris-barisnya. Fungsi murni.

	Netto dicatat sekali per tiket (`netto_2`), sedangkan satu tiket bisa memuat
	beberapa blok dengan tahun tanam berbeda. Pembagiannya mengikuti janjang.

	Kalau semua baris tiket ikut terhitung, baris terakhir menyerap sisa
	pembulatan supaya jumlah pecahan persis sama dengan netto tiketnya. Kalau
	sebagian barisnya tersaring keluar — misalnya ada blok dari unit non plasma —
	tidak ada yang menyerap sisa, jadi yang terhitung hanya sebesar porsinya.

	Balikan: list of (tahun_tanam, berat).
	"""
	if not rows:
		return []

	netto = flt(rows[0].get("netto_2"))
	if not netto:
		return []

	janjang_baris = sum(flt(row.get("jumlah_janjang")) for row in rows)
	pembagi = flt(rows[0].get("total_janjang")) or janjang_baris

	if pembagi <= 0:
		# tanpa janjang tidak ada dasar pembagian sama sekali
		return [(normalisasi_tahun_tanam(rows[0].get("tahun_tanam")), netto)]

	semua_baris_ikut = abs(janjang_baris - pembagi) < 0.001

	hasil = []
	terbagi = 0.0

	for row in rows[:-1] if semua_baris_ikut else rows:
		berat = flt(netto * flt(row.get("jumlah_janjang")) / pembagi, PRESISI_BERAT)
		terbagi += berat
		hasil.append((normalisasi_tahun_tanam(row.get("tahun_tanam")), berat))

	if semua_baris_ikut:
		hasil.append((
			normalisasi_tahun_tanam(rows[-1].get("tahun_tanam")),
			flt(netto - terbagi, PRESISI_BERAT),
		))

	return hasil


def cari_masa(masa_rows, tanggal):
	"""Masa yang memuat tanggal itu, atau None. Fungsi murni."""
	tanggal = getdate(tanggal)

	for masa in masa_rows:
		if getdate(masa["tanggal_mulai"]) <= tanggal <= getdate(masa["tanggal_selesai"]):
			return masa

	return None


def kelompokkan_per_tiket(baris):
	"""Baris timbangan dikelompokkan per tiket, urutannya dipertahankan. Fungsi murni."""
	tiket = {}

	for row in baris:
		tiket.setdefault(row.get("timbangan"), []).append(row)

	return list(tiket.values())


def kelompokkan_netto(baris_timbangan, masa_rows):
	"""Kelompokkan netto timbangan per (masa, tahun tanam). Fungsi murni — tanpa database.

	Balikan: (hasil, terlewat). `hasil` urut menurut masa lalu tahun tanam.
	`terlewat` berisi baris yang tanggalnya tidak masuk masa manapun — seharusnya
	kosong, karena pembagian masa wajib menutup satu bulan penuh.
	"""
	ember = {}
	terlewat = []

	for rows in kelompokkan_per_tiket(baris_timbangan):
		masa = cari_masa(masa_rows, rows[0].get("posting_date"))
		if not masa:
			terlewat.extend(rows)
			continue

		for tahun_tanam, berat in pecah_netto_tiket(rows):
			kunci = (cint(masa["masa_no"]), tahun_tanam)
			if kunci not in ember:
				ember[kunci] = {
					"master_harga_shu": masa.get("master_harga_shu"),
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


def ambil_baris_timbangan(company, units, tanggal_mulai, tanggal_selesai):
	"""Baris timbangan mentah dalam rentang tanggal, belum dipecah dan belum dikelompokkan.

	Netto diambil dari `netto_2` tiket timbangan, bukan dari berat yang tersalin
	ke SPB — satu tiket menyalin netto yang sama ke semua baris SPB-nya, jadi
	kalau dibaca dari sana buah satu truk bisa terhitung berkali-kali.

	Tahun tanam ikut yang tercatat di tiket, dan unitnya dibaca dari baris
	tiket karena unit di kepala tiket berisi PKS penerimanya.

	Pengelompokan sengaja tidak dilakukan di SQL: netto satu tiket bisa jatuh ke
	beberapa tahun tanam, dan pemecahannya harus bisa dites tanpa database.
	"""
	if not units:
		return []

	return frappe.db.sql(
		"""
		SELECT t.name AS timbangan, t.posting_date, t.netto_2, t.total_janjang,
		       d.blok, d.tahun_tanam, d.jumlah_janjang
		FROM `tabTimbangan SPB Detail` d
		INNER JOIN `tabTimbangan` t ON d.parent = t.name
		INNER JOIN `tabUnit` u ON d.unit = u.name
		WHERE t.docstatus = 1
		  AND t.company = %(company)s
		  AND u.plasma = 1
		  AND d.unit IN %(units)s
		  AND t.posting_date BETWEEN %(tanggal_mulai)s AND %(tanggal_selesai)s
		ORDER BY t.posting_date, t.name, d.idx
		""",
		{
			"company": company,
			"units": tuple(units),
			"tanggal_mulai": getdate(tanggal_mulai),
			"tanggal_selesai": getdate(tanggal_selesai),
		},
		as_dict=True,
	)


def jenis_bkm(doctype):
	"""Label pendek untuk kolom Jenis: "Buku Kerja Mandor Panen" → "Panen"."""
	return doctype.replace("Buku Kerja Mandor ", "")


def ambil_baris_bkm(company, units, tanggal_mulai, tanggal_selesai):
	"""Dokumen BKM yang jadi biaya mitra, satu baris per dokumen.

	Yang diambil `grand_total`, yaitu nilai penuh BKM — upah, premi, dan khusus
	perawatan materialnya juga. Bukan nilai jurnalnya: BKM Perawatan sengaja
	membuang material dari GL Entry karena sudah dijurnal Stock Entry, sedangkan
	mitra tetap ditagih material yang dipakai di kebunnya.

	Dokumen dihitung sejak disubmit, tidak menunggu workflow Posted. Posted baru
	terjadi saat Accounting Period ditutup, jauh sesudah perhitungan bulanan ini
	dibuat — menunggunya berarti biaya selalu nol.

	Dokumennya didaftar utuh, bukan langsung dijumlah di SQL, supaya angka yang
	muncul di nota bisa ditelusuri sampai ke BKM-nya satu per satu.
	"""
	if not units:
		return []

	nilai = {
		"company": company,
		"units": tuple(units),
		"tanggal_mulai": getdate(tanggal_mulai),
		"tanggal_selesai": getdate(tanggal_selesai),
	}

	baris = []

	for doctype, _fieldname in BKM_BIAYA:
		# nama doctype berasal dari BKM_BIAYA, bukan dari masukan pengguna
		rows = frappe.db.sql(
			f"""
			SELECT b.name AS voucher_no, b.posting_date, b.unit, b.divisi,
			       b.grand_total AS nilai
			FROM `tab{doctype}` b
			INNER JOIN `tabUnit` u ON b.unit = u.name
			WHERE b.docstatus = 1
			  AND b.company = %(company)s
			  AND u.plasma = 1
			  AND b.unit IN %(units)s
			  AND b.posting_date BETWEEN %(tanggal_mulai)s AND %(tanggal_selesai)s
			ORDER BY b.posting_date, b.name
			""",
			nilai,
			as_dict=True,
		)

		for row in rows:
			row["voucher_type"] = doctype
			row["jenis"] = jenis_bkm(doctype)
			row["nilai"] = flt(row["nilai"], PRESISI_UANG)
			baris.append(row)

	return baris


def rekap_biaya_bkm(baris):
	"""Total per jenis BKM dari daftar barisnya. Fungsi murni — tanpa database.

	Balikan: dict fieldname → total, satu untuk tiap jenis BKM. Dipakai baik
	untuk baris mentah dari SQL maupun untuk baris child table yang tersimpan,
	supaya angka ringkasan tidak pernah beda dari daftarnya.
	"""
	fieldname_per_doctype = dict(BKM_BIAYA)
	hasil = {fieldname: 0.0 for fieldname in fieldname_per_doctype.values()}

	for row in baris:
		fieldname = fieldname_per_doctype.get(row.get("voucher_type"))
		if fieldname:
			hasil[fieldname] += flt(row.get("nilai"))

	return {fieldname: flt(total, PRESISI_UANG) for fieldname, total in hasil.items()}


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
		"""Masa bulan ini dari Master Harga SHU. Rentang tanggal tidak pernah dihitung sendiri."""
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
					"Pembagian masa {0} {1} untuk {2} belum ada. "
					"Isi dulu tabel Masa di Master Harga SHU tahun itu — rentang tanggal "
					"perhitungan ini diambil dari situ."
				).format(self.bulan, self.tahun, self.company),
				title=_("Masa Belum Ada"),
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

	def hitung_biaya(self):
		"""Biaya Perawatan selalu jumlah ketiga nilai BKM, tidak pernah diketik tangan.

		Ketiga nilai itu sendiri dijumlah ulang dari daftar BKM-nya, jadi angka
		ringkasan tidak bisa menyimpang dari daftar yang ditampilkan.

		Lain-lain tetap manual dan ikut terpotong lewat totalnya — kalau tidak,
		angka yang diketik di situ tidak berpengaruh apa-apa.
		"""
		self.update(rekap_biaya_bkm(self.detail_biaya))

		self.biaya_perawatan = flt(
			sum(flt(self.get(fieldname)) for _, fieldname in BKM_BIAYA), PRESISI_UANG
		)
		self.total_biaya_perawatan_panen_dan_transport = flt(
			self.biaya_perawatan + flt(self.lain_lain), PRESISI_UANG
		)

	def hitung_rekap(self):
		self.total_netto = flt(sum(flt(row.netto_kg) for row in self.detail), PRESISI_BERAT)
		self.jumlah_produksi = flt(sum(flt(row.total) for row in self.detail), PRESISI_UANG)

		self.hitung_biaya()

		hasil = hitung_shu(
			self.jumlah_produksi,
			self.total_biaya_perawatan_panen_dan_transport,
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
		"""Isi ulang detail dari tiket timbangan, dan biayanya dari BKM. Tombol di form."""
		self.set_periode()
		self.validate_unit()

		units = [row.unit for row in self.unit]

		masa_rows = self.masa_bulan_ini()
		baris_timbangan = ambil_baris_timbangan(
			self.company,
			units,
			self.tanggal_mulai,
			self.tanggal_selesai,
		)
		netto, terlewat = kelompokkan_netto(baris_timbangan, masa_rows)

		self.set("detail", [])
		for baris in netto:
			self.append(
				"detail",
				{
					**baris,
					"harga": get_harga_shu(self.company, baris["tanggal_mulai"], baris["tahun_tanam"]),
				},
			)

		self.set(
			"detail_biaya",
			ambil_baris_bkm(self.company, units, self.tanggal_mulai, self.tanggal_selesai),
		)

		self.hitung_baris()
		self.hitung_rekap()
		self.set_status_harga()

		if terlewat:
			frappe.msgprint(
				_("{0} baris timbangan tanggalnya tidak masuk masa manapun dan tidak ikut dihitung.").format(
					len(terlewat)
				),
				title=_("Ada Timbangan di Luar Masa"),
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

		return {
			"jumlah_baris": len(self.detail),
			"jumlah_bkm": len(self.detail_biaya),
			"status_harga": self.status_harga,
			"biaya_perawatan": self.biaya_perawatan,
		}


@frappe.whitelist()
def get_unit_plasma(company):
	"""Semua unit plasma milik company. Dipakai untuk mengisi awal daftar unit."""
	return frappe.get_all(
		"Unit",
		filters={"company": company, "plasma": 1},
		pluck="name",
		order_by="name",
	)
