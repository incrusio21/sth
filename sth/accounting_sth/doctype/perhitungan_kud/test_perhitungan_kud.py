# Copyright (c) 2026, DAS and contributors
# See license.txt

from datetime import date

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from sth.accounting_sth.doctype.perhitungan_kud.perhitungan_kud import (
	BKM_BIAYA,
	cari_masa,
	hitung_shu,
	jenis_bkm,
	kelompokkan_netto,
	normalisasi_tahun_tanam,
	pecah_netto_tiket,
	rekap_biaya_bkm,
)


def baris_bkm(doctype, nilai, **kwargs):
	"""Satu baris rincian BKM, sebentuk dengan yang dihasilkan ambil_baris_bkm."""
	row = {
		"voucher_type": doctype,
		"jenis": jenis_bkm(doctype),
		"voucher_no": "BKM-0001",
		"posting_date": date(2026, 1, 5),
		"unit": "UNIT-PLASMA",
		"divisi": "DIV-01",
		"nilai": nilai,
	}
	row.update(kwargs)
	return row

# Pembagian masa Januari 2026 yang sungguhan, sama dengan test_master_harga_shu.
MASA_JANUARI = [
	{
		"master_harga_shu": "MHS-TML-2026",
		"masa_no": 1,
		"tanggal_mulai": date(2026, 1, 1),
		"tanggal_selesai": date(2026, 1, 2),
	},
	{
		"master_harga_shu": "MHS-TML-2026",
		"masa_no": 2,
		"tanggal_mulai": date(2026, 1, 3),
		"tanggal_selesai": date(2026, 1, 8),
	},
	{
		"master_harga_shu": "MHS-TML-2026",
		"masa_no": 3,
		"tanggal_mulai": date(2026, 1, 9),
		"tanggal_selesai": date(2026, 1, 15),
	},
]


def baris_timbangan(**kwargs):
	"""Satu baris tiket timbangan. Field yang tidak disebut diisi nilai netral.

	`netto_2` dan `total_janjang` milik tiket, jadi nilainya sama di semua baris
	satu tiket — persis seperti hasil join di ambil_baris_timbangan.
	"""
	row = {
		"timbangan": "TBG-0001",
		"posting_date": date(2026, 1, 5),
		"netto_2": 1000.0,
		"total_janjang": 100.0,
		"jumlah_janjang": 100.0,
		"blok": "A01",
		"tahun_tanam": "2012",
	}
	row.update(kwargs)
	return row


def tiket(nomor, posting_date=date(2026, 1, 5), netto_2=1000.0, baris=None):
	"""Satu tiket berisi beberapa blok. `baris` = [(tahun_tanam, janjang), ...]"""
	baris = baris or [("2012", 100.0)]
	total_janjang = sum(janjang for _, janjang in baris)

	return [
		baris_timbangan(
			timbangan=nomor,
			posting_date=posting_date,
			netto_2=netto_2,
			total_janjang=total_janjang,
			jumlah_janjang=janjang,
			tahun_tanam=tahun_tanam,
		)
		for tahun_tanam, janjang in baris
	]


class TestNormalisasiTahunTanam(FrappeTestCase):
	def test_spasi_dan_tipe_tidak_bikin_kelompok_baru(self):
		# Blok.tahun_tanam bertipe Data — semua bentuk ini harus jadi satu.
		for nilai in ("2010", " 2010", "2010 ", 2010, 2010.0):
			self.assertEqual(normalisasi_tahun_tanam(nilai), 2010)

	def test_kosong_jadi_nol(self):
		for nilai in (None, "", "   "):
			self.assertEqual(normalisasi_tahun_tanam(nilai), 0)


class TestPecahNettoTiket(FrappeTestCase):
	def test_satu_blok_netto_utuh_ke_satu_tahun_tanam(self):
		hasil = pecah_netto_tiket(tiket("TBG-0001"))
		self.assertEqual(hasil, [(2012, 1000.0)])

	def test_netto_nol_tidak_menghasilkan_baris(self):
		self.assertEqual(pecah_netto_tiket(tiket("TBG-0001", netto_2=0)), [])

	def test_tiket_kosong_tidak_meledak(self):
		self.assertEqual(pecah_netto_tiket([]), [])

	def test_dua_blok_dibagi_menurut_janjang(self):
		hasil = pecah_netto_tiket(
			tiket("TBG-0001", baris=[("2012", 70.0), ("2018", 30.0)])
		)
		self.assertEqual(hasil, [(2012, 700.0), (2018, 300.0)])

	def test_sisa_pembulatan_diserap_baris_terakhir(self):
		# 1000 dibagi 2:1 tidak habis. Yang dijaga: jumlah pecahan tetap persis 1000.
		hasil = pecah_netto_tiket(
			tiket("TBG-0001", baris=[("2012", 2.0), ("2018", 1.0)])
		)
		self.assertEqual(len(hasil), 2)
		self.assertEqual(flt(sum(berat for _, berat in hasil), 3), 1000.0)
		self.assertEqual(hasil[0], (2012, 666.667))
		self.assertEqual(hasil[1], (2018, 333.333))

	def test_baris_yang_tersaring_keluar_tidak_ikut_menyerap_netto(self):
		# Tiket 100 janjang tapi cuma 70 janjang yang unitnya plasma: yang
		# terhitung 70 persennya saja, sisanya bukan hak mitra ini.
		baris = [
			baris_timbangan(total_janjang=100.0, jumlah_janjang=70.0),
		]

		self.assertEqual(pecah_netto_tiket(baris), [(2012, 700.0)])

	def test_janjang_nol_tidak_bikin_pembagian_nol(self):
		baris = [baris_timbangan(total_janjang=0.0, jumlah_janjang=0.0)]

		self.assertEqual(pecah_netto_tiket(baris), [(2012, 1000.0)])

	def test_blok_tanpa_tahun_tanam_masuk_kelompok_nol(self):
		hasil = pecah_netto_tiket(tiket("TBG-0001", baris=[(None, 100.0)]))
		self.assertEqual(hasil, [(0, 1000.0)])


class TestKelompokkanNetto(FrappeTestCase):
	def test_gabung_per_masa_dan_tahun_tanam(self):
		rows = (
			tiket("TBG-0001", posting_date=date(2026, 1, 1), netto_2=500.0)
			+ tiket("TBG-0002", posting_date=date(2026, 1, 2), netto_2=300.0)
			+ tiket("TBG-0003", posting_date=date(2026, 1, 5), netto_2=200.0)
			+ tiket(
				"TBG-0004",
				posting_date=date(2026, 1, 5),
				netto_2=100.0,
				baris=[("2018", 100.0)],
			)
		)

		hasil, terlewat = kelompokkan_netto(rows, MASA_JANUARI)

		self.assertEqual(terlewat, [])
		self.assertEqual(
			[(b["masa_no"], b["tahun_tanam"], b["netto_kg"]) for b in hasil],
			[(1, 2012, 800.0), (2, 2012, 200.0), (2, 2018, 100.0)],
		)

	def test_dua_baris_satu_tiket_tidak_terhitung_dua_kali(self):
		# Inti pindah ke netto_2: netto dicatat sekali per tiket, bukan per baris.
		rows = tiket(
			"TBG-0001",
			posting_date=date(2026, 1, 1),
			netto_2=1000.0,
			baris=[("2012", 60.0), ("2012", 40.0)],
		)

		hasil, _ = kelompokkan_netto(rows, MASA_JANUARI)

		self.assertEqual([(b["tahun_tanam"], b["netto_kg"]) for b in hasil], [(2012, 1000.0)])

	def test_tanggal_masa_ikut_terbawa_dari_master_harga_shu(self):
		hasil, _ = kelompokkan_netto(
			tiket("TBG-0001", posting_date=date(2026, 1, 9)), MASA_JANUARI
		)

		self.assertEqual(hasil[0]["tanggal_mulai"], date(2026, 1, 9))
		self.assertEqual(hasil[0]["tanggal_selesai"], date(2026, 1, 15))
		self.assertEqual(hasil[0]["master_harga_shu"], "MHS-TML-2026")

	def test_satu_tiket_bisa_jatuh_ke_dua_tahun_tanam_dalam_satu_masa(self):
		rows = tiket(
			"TBG-0001",
			posting_date=date(2026, 1, 1),
			baris=[("2012", 70.0), ("2018", 30.0)],
		)

		hasil, _ = kelompokkan_netto(rows, MASA_JANUARI)

		self.assertEqual(
			[(b["tahun_tanam"], b["netto_kg"]) for b in hasil],
			[(2012, 700.0), (2018, 300.0)],
		)

	def test_tanggal_di_luar_semua_masa_dilaporkan_bukan_dibuang_diam_diam(self):
		rows = tiket("TBG-0001", posting_date=date(2026, 1, 20))

		hasil, terlewat = kelompokkan_netto(rows, MASA_JANUARI)

		self.assertEqual(hasil, [])
		self.assertEqual(len(terlewat), 1)

	def test_cari_masa(self):
		self.assertEqual(cari_masa(MASA_JANUARI, date(2026, 1, 2))["masa_no"], 1)
		self.assertEqual(cari_masa(MASA_JANUARI, date(2026, 1, 3))["masa_no"], 2)
		self.assertIsNone(cari_masa(MASA_JANUARI, date(2026, 1, 31)))


class TestRekapBiayaBKM(FrappeTestCase):
	def test_dikelompokkan_per_jenis_bkm(self):
		baris = [
			baris_bkm("Buku Kerja Mandor Perawatan", 10.0),
			baris_bkm("Buku Kerja Mandor Perawatan", 15.0),
			baris_bkm("Buku Kerja Mandor Panen", 20.0),
			baris_bkm("Buku Kerja Mandor Traksi", 5.0),
		]

		self.assertEqual(
			rekap_biaya_bkm(baris),
			{
				"biaya_bkm_perawatan": 25.0,
				"biaya_bkm_panen": 20.0,
				"biaya_bkm_traksi": 5.0,
			},
		)

	def test_tanpa_baris_semuanya_nol(self):
		self.assertEqual(set(rekap_biaya_bkm([]).values()), {0.0})

	def test_jenis_dipakai_cuma_sebagai_label(self):
		# Pengelompokan berpatokan voucher_type, bukan label Jenis-nya, supaya
		# label yang salah ketik tidak memindahkan angka ke kelompok lain.
		baris = [baris_bkm("Buku Kerja Mandor Panen", 20.0, jenis="Perawatan")]

		self.assertEqual(rekap_biaya_bkm(baris)["biaya_bkm_panen"], 20.0)


class TestHitungBiaya(FrappeTestCase):
	"""Biaya Perawatan dirakit dari rincian BKM, bukan diketik tangan."""

	def doc(self, baris=None, **kwargs):
		doc = frappe.new_doc("Perhitungan KUD")
		doc.update(kwargs)

		for row in baris or []:
			doc.append("detail_biaya", row)

		return doc

	def test_biaya_perawatan_jumlah_ketiga_nilai_bkm(self):
		doc = self.doc([
			baris_bkm("Buku Kerja Mandor Perawatan", 10.0),
			baris_bkm("Buku Kerja Mandor Panen", 20.0),
			baris_bkm("Buku Kerja Mandor Traksi", 5.0),
		])
		doc.hitung_biaya()

		self.assertEqual(doc.biaya_bkm_perawatan, 10.0)
		self.assertEqual(doc.biaya_bkm_panen, 20.0)
		self.assertEqual(doc.biaya_bkm_traksi, 5.0)
		self.assertEqual(doc.biaya_perawatan, 35.0)

	def test_angka_ketikan_ditimpa_hasil_rekap_rincian(self):
		# Fieldnya read-only di form, tapi jalur lain (API, impor) masih bisa
		# mengisinya. Yang berlaku tetap rincian BKM-nya.
		doc = self.doc(
			[baris_bkm("Buku Kerja Mandor Perawatan", 10.0)],
			biaya_perawatan=999.0,
			biaya_bkm_panen=888.0,
		)
		doc.hitung_biaya()

		self.assertEqual(doc.biaya_bkm_panen, 0.0)
		self.assertEqual(doc.biaya_perawatan, 10.0)

	def test_lain_lain_masuk_lewat_total(self):
		doc = self.doc([baris_bkm("Buku Kerja Mandor Perawatan", 10.0)], lain_lain=4.0)
		doc.hitung_biaya()

		self.assertEqual(doc.total_biaya_perawatan_panen_dan_transport, 14.0)

	def test_lain_lain_ikut_terpotong_di_biaya_operasional(self):
		# Kalau lain-lain tidak sampai ke hitung_shu, angkanya cuma hiasan.
		doc = self.doc(
			[baris_bkm("Buku Kerja Mandor Perawatan", 1000.0)],
			lain_lain=250.0,
			persen_management_fee=0,
		)
		doc.hitung_rekap()

		self.assertEqual(doc.jumlah_biaya_operasional, 1250.0)

	def test_semua_fieldname_bkm_ada_di_doctype(self):
		meta = frappe.get_meta("Perhitungan KUD")
		for _doctype, fieldname in BKM_BIAYA:
			self.assertTrue(meta.has_field(fieldname), msg=fieldname)

	def test_doctype_bkm_yang_didaftar_benar_ada(self):
		# Salah ketik nama doctype bikin SQL-nya menyebut tabel yang tidak ada,
		# dan itu baru ketahuan saat tombol ditekan.
		for doctype, _fieldname in BKM_BIAYA:
			self.assertTrue(frappe.db.exists("DocType", doctype), msg=doctype)


class TestHitungSHU(FrappeTestCase):
	# Angka Januari 2026 dari sheet PERHITUNGAN KUD.
	JUMLAH_PRODUKSI = 78458951.0
	BIAYA_PERAWATAN = 31654532.0

	def hitung(self, **kwargs):
		args = {
			"jumlah_produksi": self.JUMLAH_PRODUKSI,
			"biaya_perawatan": self.BIAYA_PERAWATAN,
			"persen_management_fee": 2.5,
			"persen_pph22": 0.25,
			"persen_bagi_hasil": 50,
		}
		args.update(kwargs)
		return hitung_shu(**args)

	def test_rantai_potongan_januari_2026(self):
		hasil = self.hitung()

		# Management Fee jatuh persis di titik tengah (1.961.473,775), jadi digit
		# terakhirnya ditentukan oleh Rounding Method di System Settings — bukan
		# oleh kode ini. Yang diuji: rantainya benar, bukan setelan situsnya.
		self.assertAlmostEqual(hasil["management_fee"], 1961473.775, delta=0.01)
		self.assertAlmostEqual(hasil["jumlah_biaya_operasional"], 33616005.775, delta=0.01)
		self.assertAlmostEqual(hasil["setelah_biaya_operasional"], 44842945.225, delta=0.01)
		self.assertAlmostEqual(hasil["pph22"], 196147.3775, delta=0.01)
		self.assertAlmostEqual(hasil["hasil_bersih"], 44646797.8475, delta=0.01)
		self.assertAlmostEqual(hasil["angsuran_hutang"], 22323398.92, delta=0.01)
		self.assertAlmostEqual(hasil["pembayaran_ke_mitra"], 22323398.92, delta=0.01)

	def test_selisih_terhadap_excel_tetap_di_bawah_satu_rupiah(self):
		# Excel membulatkan Management Fee ke rupiah penuh (1.961.474) tapi PPh 22
		# tidak. Di sini keduanya 2 desimal, jadi hasilnya sedikit di atas Excel.
		# Perbedaan itu disengaja — yang tidak boleh adalah selisih yang membesar.
		hasil = self.hitung()
		self.assertLess(abs(hasil["hasil_bersih"] - 44646797.6225), 1)

	def test_rantai_potongan_saling_menyambung(self):
		hasil = self.hitung()

		self.assertEqual(
			flt(self.BIAYA_PERAWATAN + hasil["management_fee"], 2),
			hasil["jumlah_biaya_operasional"],
		)
		self.assertEqual(
			flt(self.JUMLAH_PRODUKSI - hasil["jumlah_biaya_operasional"], 2),
			hasil["setelah_biaya_operasional"],
		)
		self.assertEqual(
			flt(hasil["setelah_biaya_operasional"] - hasil["pph22"], 2), hasil["hasil_bersih"]
		)

	def test_dua_bagian_selalu_berjumlah_hasil_bersih(self):
		# Termasuk persentase yang tidak habis dibagi — pembayaran dihitung sebagai
		# sisa justru supaya kasus begini tidak kehilangan satu sen pun.
		for persen in (50, 33.33, 66.67, 0, 100):
			hasil = self.hitung(persen_bagi_hasil=persen)
			self.assertEqual(
				flt(hasil["angsuran_hutang"] + hasil["pembayaran_ke_mitra"], 2),
				hasil["hasil_bersih"],
				msg=f"persen_bagi_hasil={persen}",
			)

	def test_fee_dan_pph_dihitung_dari_produksi_bukan_dari_sisa(self):
		# Kalau salah baca tata letak Excel, keduanya akan dihitung dari
		# setelah_biaya_operasional dan hasilnya jauh lebih kecil.
		hasil = self.hitung()
		self.assertAlmostEqual(hasil["pph22"], self.JUMLAH_PRODUKSI * 0.0025, delta=0.01)
		self.assertAlmostEqual(hasil["management_fee"], self.JUMLAH_PRODUKSI * 0.025, delta=0.01)
		self.assertGreater(hasil["pph22"], hasil["setelah_biaya_operasional"] * 0.0025)

	def test_produksi_nol_tidak_meledak(self):
		hasil = self.hitung(jumlah_produksi=0, biaya_perawatan=0)
		self.assertEqual(hasil["hasil_bersih"], 0)
		self.assertEqual(hasil["pembayaran_ke_mitra"], 0)

	def test_biaya_lebih_besar_dari_produksi_menghasilkan_angka_negatif(self):
		# Tidak dicegah di sini — yang penting tandanya konsisten sampai ke bawah,
		# bukan diam-diam jadi nol.
		hasil = self.hitung(biaya_perawatan=100000000.0)
		self.assertLess(hasil["hasil_bersih"], 0)
		self.assertEqual(
			flt(hasil["angsuran_hutang"] + hasil["pembayaran_ke_mitra"], 2), hasil["hasil_bersih"]
		)
