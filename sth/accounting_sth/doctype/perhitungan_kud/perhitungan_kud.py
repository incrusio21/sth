# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import erpnext
import frappe
from erpnext.accounts.general_ledger import make_gl_entries, make_reverse_gl_entries
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

# Susunan jurnal: satu debit sebesar seluruh pembelian, lalu kredit yang
# memecahnya sampai habis. Urutannya mengikuti Jurnal KUD.xlsx.
#
# (kunci akun di setelan, field nilai di dokumen, sisi, keterangan)
#
# Jumlahnya seimbang dengan sendirinya: hitung_shu() menyusun Hasil Bersih
# sebagai sisa Jumlah Produksi dikurangi biaya, fee, dan PPh 22, lalu memecahnya
# jadi Angsuran Hutang dan Pembayaran ke Mitra — juga sebagai sisa. Jadi kelima
# kredit selalu berjumlah persis Jumlah Produksi tanpa baris pembulatan.
BARIS_JURNAL = (
	("akun_pembelian_tbs", "jumlah_produksi", "debit", "Pembelian TBS Plasma"),
	(
		"akun_biaya_plasma",
		"total_biaya_perawatan_panen_dan_transport",
		"credit",
		"Biaya Perawatan, Panen & Transport",
	),
	("akun_management_fee", "management_fee", "credit", "Management Fee"),
	("akun_pph22", "pph22", "credit", "PPh Pasal 22"),
	("akun_piutang_plasma", "angsuran_hutang", "credit", "Angsuran Hutang Mitra"),
	("akun_hutang_plasma_antara", "pembayaran_ke_mitra", "credit", "Pembayaran ke Mitra"),
)

# Tidak ada baris jurnal ini yang membawa party. Hutang ke mitra berhenti di
# akun antara tanpa party, lalu Purchase Invoice yang menariknya memindahkannya
# ke 2111091 lengkap dengan supplier-nya. Kalau party dipasang di dua tempat,
# umur hutang mitra terhitung dua kali.


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


def baris_jurnal_biaya(total, pembalikan, akun_kontra):
	"""Baris kredit untuk Biaya Perawatan, Panen & Transport. Fungsi murni.

	Biaya mitra dikembalikan ke akun biayanya sendiri sampai saldonya nol —
	itulah `pembalikan`, satu baris per (akun, cost center) yang tersentuh BKM
	di perhitungan ini. Sisanya, yaitu bagian yang GL-nya belum lahir karena
	BKM-nya belum Posted, tetap dikredit ke akun kontra supaya jurnal seimbang
	dan mitra tetap ditagih penuh.

	Saldo akun kontra karena itu bisa dibaca sebagai berapa biaya BKM yang belum
	masuk buku besar. Begitu BKM-nya Posted, debitnya muncul di akun aslinya dan
	tidak ikut terbalas lagi — penyelesaiannya di luar dokumen ini.

	Pembalikan yang jumlahnya melampaui total biaya tidak dipotong: kalau itu
	terjadi, akun kontra jadi debit dan selisihnya kelihatan, bukan tersembunyi.
	"""
	baris = []
	terbalas = 0.0

	for row in pembalikan or []:
		jumlah = flt(row.get("jumlah"), PRESISI_UANG)
		if not jumlah:
			continue

		terbalas += jumlah
		baris.append({
			"account": row.get("account"),
			"cost_center": row.get("cost_center"),
			# Saldo kredit pada akun biaya itu ganjil, tapi kalau ada, menolkannya
			# berarti mendebit. Tandanya diikuti, bukan dipaksa ke satu sisi.
			"debit": -jumlah if jumlah < 0 else 0.0,
			"credit": jumlah if jumlah > 0 else 0.0,
			"keterangan": _("Nol-kan biaya {0}").format(row.get("account")),
			"kunci": "pembalikan",
		})

	sisa = flt(flt(total, PRESISI_UANG) - terbalas, PRESISI_UANG)
	if sisa:
		baris.append({
			"account": akun_kontra,
			"cost_center": None,
			"debit": -sisa if sisa < 0 else 0.0,
			"credit": sisa if sisa > 0 else 0.0,
			"keterangan": _("Biaya Perawatan, Panen & Transport belum masuk buku besar"),
			"kunci": "akun_biaya_plasma",
		})

	return baris


def susun_baris_jurnal(nilai, akun, pembalikan=None):
	"""Baris jurnal dari nilai dokumen dan peta akun. Fungsi murni — tanpa database.

	`nilai` cukup punya field angka Perhitungan KUD, `akun` memetakan kunci di
	BARIS_JURNAL ke nama akun. Baris bernilai nol dibuang: kalau mitra kebetulan
	tidak punya biaya BKM bulan itu, jurnalnya tidak perlu baris kosong.

	Nilai negatif pindah sisi, bukan dicatat sebagai debit negatif — GL Entry
	menolak angka minus. Ini terjadi kalau biaya melampaui produksi, dan
	hitung_shu() memang sengaja membiarkan hasilnya negatif.

	`pembalikan` memecah baris biaya jadi penolan per akun, lihat
	baris_jurnal_biaya(). Totalnya tetap sama, jadi jurnalnya tetap seimbang.

	Balikan: list of dict {account, cost_center, debit, credit, keterangan, kunci}.
	"""
	baris = []

	for kunci, fieldname, sisi, keterangan in BARIS_JURNAL:
		jumlah = flt(nilai.get(fieldname), PRESISI_UANG)

		if kunci == "akun_biaya_plasma":
			baris.extend(baris_jurnal_biaya(jumlah, pembalikan, akun.get(kunci)))
			continue

		if not jumlah:
			continue

		if jumlah < 0:
			sisi = "credit" if sisi == "debit" else "debit"
			jumlah = -jumlah

		baris.append({
			"account": akun.get(kunci),
			"cost_center": None,
			"debit": jumlah if sisi == "debit" else 0.0,
			"credit": jumlah if sisi == "credit" else 0.0,
			"keterangan": keterangan,
			"kunci": kunci,
		})

	return baris


class PerhitunganKUD(Document):
	def autoname(self):
		abbr = frappe.get_cached_value("Company", self.company, "abbr")
		bulan_no = BULAN_MAP.get(self.bulan)
		if not bulan_no:
			frappe.throw(_("Bulan tidak dikenali: {0}").format(self.bulan))

		self.name = f"PK-{abbr}-{cint(self.tahun):04d}-{bulan_no:02d}-{self.mitra}"

	def onload(self):
		# Dipakai tombol Buat di form: kalau turunannya sudah ada, tombolnya
		# berubah jadi pembuka dokumen itu, bukan pembuat yang kedua.
		if self.docstatus == 1:
			self.set_onload("turunan", turunan_yang_ada(self.name))

	def validate(self):
		self.set_periode()
		self.validate_unit()
		self.validate_duplikat()
		self.isi_akun_dari_setelan()
		self.hitung_baris()
		self.hitung_rekap()
		self.set_status_harga()
		self.susun_pratinjau_jurnal()

	def on_submit(self):
		self.validate_semua_baris_berharga()
		self.make_gl_entry()

	def on_cancel(self):
		self.ignore_linked_doctypes = ("GL Entry",)
		self.make_gl_entry()

	def on_trash(self):
		frappe.db.delete("GL Entry", {
			"voucher_type": self.doctype,
			"voucher_no": self.name,
		})

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

	# ------------------------------------------------------------------
	# Jurnal
	# ------------------------------------------------------------------

	def isi_akun_dari_setelan(self):
		"""Isi akun yang masih kosong dari STH Accounting Settings.

		Yang sudah terisi tidak pernah ditimpa — itu inti dari membawa akunnya ke
		dokumen: setelan cuma memberi nilai awal, dokumen yang menentukan. Karena
		yang diisi cuma yang kosong, fungsi ini boleh dipanggil berkali-kali.
		"""
		setelan = get_setelan_kud(self.company)

		if setelan:
			for kunci in (*KOLOM_AKUN_SETELAN, "cost_center"):
				if not self.get(kunci):
					self.set(kunci, setelan.get(kunci))

		if self.mitra and not self.akun_piutang_plasma:
			self.akun_piutang_plasma = get_akun_piutang_plasma(
				self.company, self.mitra, lempar=False
			)

		if not self.cost_center:
			self.cost_center = erpnext.get_default_cost_center(self.company)

	def pembalikan_biaya(self):
		"""Saldo akun biaya yang dinolkan jurnal ini.

		Dibaca ulang tiap kali, bukan disimpan: BKM yang Posted bertambah terus
		sampai periode ditutup, jadi angkanya memang bergerak sampai dokumen ini
		disubmit. Yang berlaku adalah keadaan saat submit.
		"""
		return saldo_bkm_di_kepala_akun(self.company, self.detail_biaya)

	def susun_pratinjau_jurnal(self):
		"""Isi tabel Jurnal di tab Akun & Jurnal, apa adanya menurut isi dokumen.

		Dipakai fungsi yang sama dengan yang membuat GL Entry, jadi pratinjau
		tidak bisa berbeda dari jurnal sungguhannya. Akun yang masih kosong
		dibiarkan kosong di sini — biar kelihatan mana yang belum diisi, bukan
		melempar error waktu menyimpan.
		"""
		akun = {kunci: self.get(kunci) for kunci, *_ in BARIS_JURNAL}
		baris = susun_baris_jurnal(self.as_dict(), akun, self.pembalikan_biaya())

		# `kunci` cuma penanda internal susun_baris_jurnal, bukan kolom tabelnya.
		self.set(
			"jurnal_preview",
			[{k: v for k, v in row.items() if k != "kunci"} for row in baris],
		)

		self.total_jurnal_debit = flt(sum(row["debit"] for row in baris), PRESISI_UANG)
		self.total_jurnal_kredit = flt(sum(row["credit"] for row in baris), PRESISI_UANG)

		tanpa_akun = [row["keterangan"] for row in baris if not row["account"]]

		if not baris:
			self.status_jurnal = _("Belum ada angka, jurnal masih kosong")
		elif tanpa_akun:
			self.status_jurnal = _("Akun belum diisi: {0}").format(", ".join(tanpa_akun))
		elif self.total_jurnal_debit != self.total_jurnal_kredit:
			self.status_jurnal = _("Tidak seimbang, selisih {0}").format(
				flt(self.total_jurnal_debit - self.total_jurnal_kredit, PRESISI_UANG)
			)
		else:
			self.status_jurnal = _("{0} baris, seimbang").format(len(baris))

	def peta_akun(self):
		"""Akun tiap baris jurnal, dibaca dari dokumen ini — bukan dari setelan.

		Setelan hanya memberi nilai awal lewat isi_akun_dari_setelan(). Begitu
		dokumen disubmit, yang berlaku persis apa yang tercatat di sini, jadi
		setelan yang berubah belakangan tidak menggeser jurnal yang sudah jadi.
		"""
		akun = {kunci: self.get(kunci) for kunci, *_ in BARIS_JURNAL}

		# Baris bernilai nol tidak masuk jurnal, jadi akunnya juga tidak wajib.
		kosong = [
			keterangan
			for kunci, fieldname, _sisi, keterangan in BARIS_JURNAL
			if not akun.get(kunci) and flt(self.get(fieldname))
		]
		if kosong:
			frappe.throw(
				_(
					"Akun untuk baris ini belum diisi: {0}. "
					"Lengkapi di bagian <b>Akun Jurnal</b> dokumen ini, atau isi setelannya "
					"di STH Accounting Settings lalu tarik produksi ulang."
				).format(", ".join(kosong)),
				title=_("Akun Jurnal Belum Lengkap"),
			)

		return akun

	def make_gl_entry(self):
		if self.docstatus == 1:
			make_gl_entries(self.get_gl_entries(), merge_entries=False)
			frappe.msgprint(_("Jurnal Perhitungan KUD dibuat."), indicator="green", alert=True)
		elif self.docstatus == 2:
			make_reverse_gl_entries(voucher_type=self.doctype, voucher_no=self.name)
			frappe.msgprint(_("Jurnal Perhitungan KUD dibatalkan."), indicator="orange", alert=True)

	def get_gl_entries(self):
		akun = self.peta_akun()

		cost_center = self.cost_center or get_cost_center_kud(self.company)

		baris = susun_baris_jurnal(self.as_dict(), akun, self.pembalikan_biaya())
		if not baris:
			return []

		total_debit = flt(sum(row["debit"] for row in baris), PRESISI_UANG)
		total_credit = flt(sum(row["credit"] for row in baris), PRESISI_UANG)
		if total_debit != total_credit:
			# Tidak seharusnya terjadi: hitung_shu() memecah Jumlah Produksi
			# sampai habis. Kalau muncul, ada field yang diubah di luar validate.
			frappe.throw(
				_("Debit ({0}) dan Kredit ({1}) tidak seimbang. Simpan ulang dokumennya.").format(
					total_debit, total_credit
				),
				title=_("Jurnal Tidak Seimbang"),
			)

		gl_entries = []
		for row in baris:
			args = {
				"account": row["account"],
				# Penolan mendarat di cost center biayanya sendiri; baris lain
				# ikut cost center dokumen.
				"cost_center": row.get("cost_center") or cost_center,
				"debit": row["debit"],
				"credit": row["credit"],
				"debit_in_account_currency": row["debit"],
				"credit_in_account_currency": row["credit"],
				"remarks": "{0} - {1}".format(row["keterangan"], self.name),
			}

			gl_entries.append(self.get_gl_dict(args))

		return gl_entries

	def get_gl_dict(self, args):
		gl_dict = frappe._dict({
			"company": self.company,
			"posting_date": self.tanggal_selesai,
			"voucher_type": self.doctype,
			"voucher_no": self.name,
			"remarks": "Perhitungan KUD {0}".format(self.name),
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

	@frappe.whitelist()
	def tarik_produksi(self):
		"""Isi ulang detail dari tiket timbangan, dan biayanya dari BKM. Tombol di form."""
		self.set_periode()
		self.validate_unit()
		self.isi_akun_dari_setelan()

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


# ---------------------------------------------------------------------------
# Setelan akun jurnal
# ---------------------------------------------------------------------------

# Kolom setelan yang isinya akun, jadi padanannya di company lain bisa dicari
# lewat nomor akun. cost_center dan item_purchase_invoice tidak ikut: cost
# center milik company masing-masing dan tidak bernomor, item-nya sudah berlaku
# lintas company.
KOLOM_AKUN_SETELAN = (
	"akun_pembelian_tbs",
	"akun_biaya_plasma",
	"akun_management_fee",
	"akun_pph22",
	"akun_hutang_plasma_antara",
	"akun_hutang_mitra",
)


def akun_bernomor_sama(account, company, is_group=0):
	"""Akun di `company` yang nomornya sama dengan `account`, atau None.

	COA semua company disalin dari bagan yang sama — nomornya identik, yang beda
	cuma abbr di belakang nama. Jadi setelan cukup diisi untuk satu company dan
	sisanya bisa mengikutinya lewat nomor.
	"""
	if not account:
		return None

	nomor = frappe.get_cached_value("Account", account, "account_number")
	if not nomor:
		return None

	return frappe.db.get_value(
		"Account", {"account_number": nomor, "company": company, "is_group": is_group}, "name"
	)


def setelan_kud_rows():
	return frappe.get_single("STH Accounting Settings").get("sth_accounting_settings_kud") or []


def get_setelan_kud(company):
	"""Setelan akun jurnal KUD untuk company itu, atau None kalau tabelnya kosong.

	Baris company sendiri dipakai apa adanya. Kalau belum ada, dipakai baris
	company mana pun lalu tiap akunnya dicari padanannya lewat nomor. Akibatnya
	tabel setelan cukup diisi sekali, dan company yang COA-nya menyimpang tetap
	bisa diberi barisnya sendiri.

	cost_center tidak bisa ikut nomor, jadi dikosongkan kalau barisnya milik
	company lain — pemanggilnya jatuh ke cost center bawaan company.
	"""
	if not company:
		return None

	rows = setelan_kud_rows()
	if not rows:
		return None

	for row in rows:
		if row.company == company:
			return row

	contoh = rows[0]
	ikut_nomor = frappe._dict(contoh.as_dict())
	ikut_nomor.company = company
	ikut_nomor.cost_center = None

	for kunci in KOLOM_AKUN_SETELAN:
		ikut_nomor[kunci] = akun_bernomor_sama(contoh.get(kunci), company)

	return ikut_nomor


def get_akun_piutang_plasma(company, mitra, lempar=True):
	"""Akun Piutang Plasma milik mitra itu.

	Sama seperti setelan akun: baris (company, mitra) dipakai apa adanya, dan
	kalau belum ada, baris mitra itu di company lain diikuti lewat nomor akun.
	Nomornya memang membedakan mitra — 1293001 KUD MITRA DASAL, 1293002 BUMDES
	JABUNG CIPTA USAHA — dan nomor yang sama ada di semua company.

	`lempar=False` dipakai waktu mengisi dokumen, karena di situ akun yang belum
	ketemu masih boleh diisi tangan. Yang menjaga tetap validasi submit.
	"""
	rows = frappe.get_single("STH Accounting Settings").get("sth_accounting_settings_kud_mitra") or []

	for row in rows:
		if row.mitra == mitra and row.company == company:
			return row.akun_piutang_plasma

	for row in rows:
		if row.mitra == mitra:
			if akun := akun_bernomor_sama(row.akun_piutang_plasma, company):
				return akun

	if not lempar:
		return None

	frappe.throw(
		_(
			"Akun Piutang Plasma untuk mitra {0} di {1} belum didaftarkan. "
			"Tambahkan barisnya di tabel <b>Perhitungan KUD - Piutang Plasma per Mitra</b> "
			"di STH Accounting Settings, atau isi langsung akunnya di dokumen ini."
		).format(mitra, company),
		title=_("Akun Piutang Plasma Belum Ada"),
	)


def get_cost_center_kud(company, setelan=None):
	"""Cost center untuk jurnal dan Purchase Invoice KUD."""
	cost_center = (setelan.get("cost_center") if setelan else None) or erpnext.get_default_cost_center(
		company
	)

	if not cost_center:
		frappe.throw(
			_("Cost Center untuk {0} belum diatur, baik di setelan Perhitungan KUD maupun di Company.").format(
				company
			),
			title=_("Cost Center Belum Ada"),
		)

	return cost_center


# ---------------------------------------------------------------------------
# Dokumen turunan
#
# Dua baris jurnal KUD sengaja tidak berhenti di akun akhirnya:
#
#   Management Fee     dikredit ke 9190399, lalu Nota Piutang mendebitnya lagi
#                      dan mengkredit 1162099 PIUTANG LAINNYA.
#   Pembayaran ke Mitra dikredit ke akun antara, lalu Purchase Invoice
#                      mendebit akun antara itu dan mengkredit 2111091 dengan
#                      supplier-nya, supaya hutangnya jadi tagihan yang bisa
#                      dipilih Payment Entry.
#
# Keduanya dibuat dari sini, bukan dari dokumen tujuan, supaya angkanya tidak
# bisa menyimpang dari sumbernya.
# ---------------------------------------------------------------------------

# (doctype tujuan, field nilai di Perhitungan KUD)
TURUNAN = (
	("Nota Piutang", "management_fee"),
	("Purchase Invoice", "pembayaran_ke_mitra"),
)


def turunan_yang_ada(perhitungan_kud):
	"""Nama dokumen turunan yang sudah dibuat dan belum dibatalkan, per doctype."""
	hasil = {}

	for doctype, _fieldname in TURUNAN:
		hasil[doctype] = frappe.db.get_value(
			doctype,
			{"perhitungan_kud": perhitungan_kud, "docstatus": ("!=", 2)},
			"name",
		)

	return hasil


def siapkan_turunan(source_name, doctype, fieldname):
	"""Penjagaan yang sama untuk kedua dokumen turunan.

	Balikan: (doc Perhitungan KUD, baris setelan atau None, nilai).
	"""
	doc = frappe.get_doc("Perhitungan KUD", source_name)
	doc.check_permission("read")

	if doc.docstatus != 1:
		frappe.throw(
			_("Perhitungan KUD {0} belum disubmit.").format(source_name),
			title=_("Belum Disubmit"),
		)

	nilai = flt(doc.get(fieldname), PRESISI_UANG)
	if nilai <= 0:
		frappe.throw(
			_("{0} di {1} bernilai {2}, tidak ada yang perlu ditagihkan.").format(
				_(doctype), source_name, nilai
			),
			title=_("Nilainya Nol"),
		)

	sudah_ada = turunan_yang_ada(source_name).get(doctype)
	if sudah_ada:
		frappe.throw(
			_("{0} {1} sudah dibuat dari perhitungan ini. Batalkan dulu kalau mau membuat yang baru.").format(
				_(doctype), sudah_ada
			),
			title=_("Sudah Pernah Dibuat"),
		)

	# Setelan boleh kosong: akun jurnalnya sudah tercatat di dokumen, dan yang
	# masih dibutuhkan dari sini cuma Item Purchase Invoice.
	return doc, get_setelan_kud(doc.company), nilai


def peringatkan_po_wajib(mitra):
	"""Ingatkan kalau Buying Settings mewajibkan PO dan mitra ini belum dikecualikan.

	Tidak melempar: draftnya tetap boleh dibuat, yang gagal nanti submit-nya.
	Lebih baik ketahuan di sini daripada sesudah orang mengisi seluruh form.
	"""
	if frappe.db.get_single_value("Buying Settings", "po_required") != "Yes":
		return

	if frappe.get_cached_value(
		"Supplier", mitra, "allow_purchase_invoice_creation_without_purchase_order"
	):
		return

	frappe.msgprint(
		_(
			"Buying Settings mewajibkan Purchase Order, dan mitra {0} belum dicentang "
			"<b>Allow Purchase Invoice Creation Without Purchase Order</b>. "
			"Invoice ini bisa disimpan tapi tidak bisa disubmit sebelum centang itu dipasang."
		).format(mitra),
		title=_("Purchase Order Diwajibkan"),
		indicator="orange",
	)


@frappe.whitelist()
def buat_nota_piutang(source_name):
	"""Nota Piutang penagih Management Fee. Dipanggil lewat make_mapped_doc, belum tersimpan."""
	doc, _setelan, nilai = siapkan_turunan(source_name, "Nota Piutang", "management_fee")

	nota = frappe.new_doc("Nota Piutang")
	nota.company = doc.company
	nota.date = doc.tanggal_selesai
	nota.tipe = "Others"
	nota.sub_tipe_others = "Management Fee KUD"
	nota.perhitungan_kud = doc.name
	nota.nilai_management_fee = nilai
	nota.keterangan = _("Management Fee {0}% {1} {2} - {3}").format(
		flt(doc.persen_management_fee), doc.bulan, doc.tahun, doc.mitra
	)

	return nota


@frappe.whitelist()
def buat_purchase_invoice(source_name):
	"""Purchase Invoice tagihan mitra. Dipanggil lewat make_mapped_doc, belum tersimpan."""
	doc, setelan, nilai = siapkan_turunan(source_name, "Purchase Invoice", "pembayaran_ke_mitra")

	if not (setelan and setelan.item_purchase_invoice):
		frappe.throw(
			_("Item Purchase Invoice untuk {0} belum diatur di setelan Perhitungan KUD.").format(
				doc.company
			),
			title=_("Item Belum Diatur"),
		)

	if not doc.akun_hutang_plasma_antara:
		frappe.throw(
			_(
				"Akun Hutang Plasma Belum Ditagih di {0} kosong, jadi tidak ada yang bisa "
				"didebit invoice ini."
			).format(source_name),
			title=_("Akun Jurnal Belum Lengkap"),
		)

	if frappe.get_cached_value("Item", setelan.item_purchase_invoice, "is_stock_item"):
		frappe.throw(
			_("Item {0} adalah item stok, jadi invoice-nya akan menuntut Purchase Receipt. "
			  "Pakai item non stok di setelan Perhitungan KUD.").format(setelan.item_purchase_invoice),
			title=_("Item Harus Non Stok"),
		)

	peringatkan_po_wajib(doc.mitra)

	keterangan = _("Pembayaran plasma {0} {1} - {2}").format(doc.bulan, doc.tahun, doc.mitra)

	pi = frappe.new_doc("Purchase Invoice")
	pi.company = doc.company
	pi.supplier = doc.mitra
	pi.posting_date = doc.tanggal_selesai
	pi.perhitungan_kud = doc.name
	# bill_no dan bill_date wajib di app ini (property setter), jadi diisi dari
	# perhitungannya sendiri supaya draftnya tidak langsung merah.
	pi.bill_no = doc.name
	pi.bill_date = doc.tanggal_selesai
	pi.keterangan = keterangan

	# Akun diambil dari dokumennya, bukan dari setelan: di situlah orang
	# menggantinya kalau perhitungan ini perlu akun lain.
	if doc.akun_hutang_mitra:
		pi.credit_to = doc.akun_hutang_mitra

	pi.append(
		"items",
		{
			"item_code": setelan.item_purchase_invoice,
			"qty": 1,
			"rate": nilai,
			"description": keterangan,
			"expense_account": doc.akun_hutang_plasma_antara,
			"cost_center": doc.cost_center or get_cost_center_kud(doc.company),
		},
	)

	return pi


# ---------------------------------------------------------------------------
# Penolan akun biaya
# ---------------------------------------------------------------------------

def get_kepala_akun_kud(company):
	"""Kepala akun biaya yang saldonya dinolkan, untuk company itu.

	Sama seperti setelan akun lainnya: baris company sendiri dipakai apa adanya,
	dan kalau belum ada, baris company lain diikuti lewat nomor akun.
	"""
	rows = (
		frappe.get_single("STH Accounting Settings").get("sth_accounting_settings_kud_kepala_akun")
		or []
	)

	milik_sendiri = [row.kepala_akun for row in rows if row.company == company and row.kepala_akun]
	if milik_sendiri:
		return sorted(set(milik_sendiri))

	ikut_nomor = [
		akun
		for row in rows
		if (akun := akun_bernomor_sama(row.kepala_akun, company, is_group=1))
	]

	return sorted(set(ikut_nomor))


def akun_di_bawah(kepala, company):
	"""Semua akun non grup di bawah kepala-kepala akun itu."""
	akun = set()

	for grup in kepala:
		batas = frappe.db.get_value("Account", grup, ["lft", "rgt"])
		if not batas:
			continue

		lft, rgt = batas
		akun.update(
			frappe.get_all(
				"Account",
				filters={
					"company": company,
					"is_group": 0,
					"lft": (">=", lft),
					"rgt": ("<=", rgt),
				},
				pluck="name",
			)
		)

	return akun


def saldo_bkm_di_kepala_akun(company, baris_bkm, kepala=None):
	"""Saldo tiap (akun, cost center) yang tersentuh BKM di perhitungan ini.

	Yang dibaca GL Entry milik BKM yang terdaftar di Rincian Biaya BKM, bukan
	semua GL di cost center unit plasma. Cuma dokumen-dokumen itu yang biayanya
	ditagihkan ke mitra; menolkan yang lain berarti menghapus biaya inti yang
	kebetulan menumpang cost center sama.

	Cost center ikut dikelompokkan supaya penolannya mendarat persis di tempat
	biayanya muncul — kalau tidak, akunnya nol secara total tapi tiap cost center
	jadi punya saldo palsu.

	Balikan: list of dict {account, cost_center, jumlah}, urut dan tanpa nol.
	"""
	if not baris_bkm:
		return []

	if kepala is None:
		kepala = get_kepala_akun_kud(company)

	akun = akun_di_bawah(kepala, company)
	if not akun:
		return []

	voucher_no = sorted({row.voucher_no for row in baris_bkm if row.voucher_no})
	voucher_type = sorted({row.voucher_type for row in baris_bkm if row.voucher_type})
	if not voucher_no or not voucher_type:
		return []

	rows = frappe.db.sql(
		"""
		SELECT account, cost_center, SUM(debit) - SUM(credit) AS saldo
		FROM `tabGL Entry`
		WHERE company = %(company)s
		  AND is_cancelled = 0
		  AND voucher_type IN %(voucher_type)s
		  AND voucher_no IN %(voucher_no)s
		  AND account IN %(account)s
		GROUP BY account, cost_center
		HAVING saldo <> 0
		ORDER BY account, cost_center
		""",
		{
			"company": company,
			"voucher_type": tuple(voucher_type),
			"voucher_no": tuple(voucher_no),
			"account": tuple(akun),
		},
		as_dict=True,
	)

	return [
		{"account": row.account, "cost_center": row.cost_center, "jumlah": flt(row.saldo, PRESISI_UANG)}
		for row in rows
	]
