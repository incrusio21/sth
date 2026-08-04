# Copyright (c) 2026, DAS and contributors
# See license.txt

from datetime import date

from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from sth.plantation.doctype.perhitungan_kud.perhitungan_kud import (
	cari_masa,
	hitung_shu,
	kelompokkan_netto,
	normalisasi_tahun_tanam,
	pecah_berat_baris,
)

# Pembagian masa Januari 2026 yang sungguhan, sama dengan test_masa_shu.
MASA_JANUARI = [
	{
		"masa_shu": "MS-TML-2026-01",
		"masa_no": 1,
		"tanggal_mulai": date(2026, 1, 1),
		"tanggal_selesai": date(2026, 1, 2),
	},
	{
		"masa_shu": "MS-TML-2026-01",
		"masa_no": 2,
		"tanggal_mulai": date(2026, 1, 3),
		"tanggal_selesai": date(2026, 1, 8),
	},
	{
		"masa_shu": "MS-TML-2026-01",
		"masa_no": 3,
		"tanggal_mulai": date(2026, 1, 9),
		"tanggal_selesai": date(2026, 1, 15),
	},
]


def baris_spb(**kwargs):
	"""Baris SPB minimal. Field yang tidak disebut diisi nilai netral."""
	row = {
		"posting_date": date(2026, 1, 5),
		"qty": 100.0,
		"qty_restan": 0.0,
		"total_janjang": 100.0,
		"total_weight": 1000.0,
		"blok": "A01",
		"blok_restan": None,
		"tahun_tanam": "2012",
		"tahun_tanam_restan": None,
	}
	row.update(kwargs)
	return row


class TestNormalisasiTahunTanam(FrappeTestCase):
	def test_spasi_dan_tipe_tidak_bikin_kelompok_baru(self):
		# Blok.tahun_tanam bertipe Data — semua bentuk ini harus jadi satu.
		for nilai in ("2010", " 2010", "2010 ", 2010, 2010.0):
			self.assertEqual(normalisasi_tahun_tanam(nilai), 2010)

	def test_kosong_jadi_nol(self):
		for nilai in (None, "", "   "):
			self.assertEqual(normalisasi_tahun_tanam(nilai), 0)


class TestPecahBeratBaris(FrappeTestCase):
	def test_tanpa_restan_berat_utuh_ke_satu_tahun_tanam(self):
		hasil = pecah_berat_baris(baris_spb())
		self.assertEqual(hasil, [(2012, 1000.0)])

	def test_berat_nol_tidak_menghasilkan_baris(self):
		self.assertEqual(pecah_berat_baris(baris_spb(total_weight=0)), [])

	def test_restan_tahun_tanam_sama_tidak_dipecah(self):
		# Dipecah pun akan digabung lagi; memecah hanya menambah peluang salah bulat.
		hasil = pecah_berat_baris(
			baris_spb(
				blok_restan="A02",
				qty=70.0,
				qty_restan=30.0,
				tahun_tanam_restan="2012",
			)
		)
		self.assertEqual(hasil, [(2012, 1000.0)])

	def test_restan_tahun_tanam_beda_dipecah_menurut_janjang(self):
		hasil = pecah_berat_baris(
			baris_spb(
				blok_restan="B01",
				qty=70.0,
				qty_restan=30.0,
				tahun_tanam_restan="2018",
			)
		)
		self.assertEqual(hasil, [(2012, 700.0), (2018, 300.0)])

	def test_sisa_pembulatan_diserap_blok_utama(self):
		# 1000 dibagi 2:1 tidak habis. Yang dijaga: jumlah pecahan tetap persis 1000.
		hasil = pecah_berat_baris(
			baris_spb(
				blok_restan="B01",
				qty=2.0,
				qty_restan=1.0,
				total_janjang=3.0,
				tahun_tanam_restan="2018",
			)
		)
		self.assertEqual(len(hasil), 2)
		self.assertEqual(flt(sum(berat for _, berat in hasil), 3), 1000.0)
		self.assertEqual(hasil[1], (2018, 333.333))
		self.assertEqual(hasil[0], (2012, 666.667))

	def test_total_janjang_nol_tidak_bikin_pembagian_nol(self):
		hasil = pecah_berat_baris(
			baris_spb(
				blok_restan="B01",
				qty=0.0,
				qty_restan=0.0,
				total_janjang=0.0,
				tahun_tanam_restan="2018",
			)
		)
		self.assertEqual(hasil, [(2012, 1000.0)])

	def test_blok_tanpa_tahun_tanam_masuk_kelompok_nol(self):
		hasil = pecah_berat_baris(baris_spb(tahun_tanam=None))
		self.assertEqual(hasil, [(0, 1000.0)])


class TestKelompokkanNetto(FrappeTestCase):
	def test_gabung_per_masa_dan_tahun_tanam(self):
		rows = [
			baris_spb(posting_date=date(2026, 1, 1), total_weight=500.0),
			baris_spb(posting_date=date(2026, 1, 2), total_weight=300.0),
			baris_spb(posting_date=date(2026, 1, 5), total_weight=200.0),
			baris_spb(posting_date=date(2026, 1, 5), total_weight=100.0, tahun_tanam="2018"),
		]

		hasil, terlewat = kelompokkan_netto(rows, MASA_JANUARI)

		self.assertEqual(terlewat, [])
		self.assertEqual(
			[(b["masa_no"], b["tahun_tanam"], b["netto_kg"]) for b in hasil],
			[(1, 2012, 800.0), (2, 2012, 200.0), (2, 2018, 100.0)],
		)

	def test_tanggal_masa_ikut_terbawa_dari_masa_shu(self):
		hasil, _ = kelompokkan_netto([baris_spb(posting_date=date(2026, 1, 9))], MASA_JANUARI)

		self.assertEqual(hasil[0]["tanggal_mulai"], date(2026, 1, 9))
		self.assertEqual(hasil[0]["tanggal_selesai"], date(2026, 1, 15))
		self.assertEqual(hasil[0]["masa_shu"], "MS-TML-2026-01")

	def test_restan_bisa_jatuh_ke_dua_tahun_tanam_dalam_satu_masa(self):
		rows = [
			baris_spb(
				posting_date=date(2026, 1, 1),
				blok_restan="B01",
				qty=70.0,
				qty_restan=30.0,
				tahun_tanam_restan="2018",
			)
		]

		hasil, _ = kelompokkan_netto(rows, MASA_JANUARI)

		self.assertEqual(
			[(b["tahun_tanam"], b["netto_kg"]) for b in hasil],
			[(2012, 700.0), (2018, 300.0)],
		)

	def test_tanggal_di_luar_semua_masa_dilaporkan_bukan_dibuang_diam_diam(self):
		rows = [baris_spb(posting_date=date(2026, 1, 20))]

		hasil, terlewat = kelompokkan_netto(rows, MASA_JANUARI)

		self.assertEqual(hasil, [])
		self.assertEqual(len(terlewat), 1)

	def test_cari_masa(self):
		self.assertEqual(cari_masa(MASA_JANUARI, date(2026, 1, 2))["masa_no"], 1)
		self.assertEqual(cari_masa(MASA_JANUARI, date(2026, 1, 3))["masa_no"], 2)
		self.assertIsNone(cari_masa(MASA_JANUARI, date(2026, 1, 31)))


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
