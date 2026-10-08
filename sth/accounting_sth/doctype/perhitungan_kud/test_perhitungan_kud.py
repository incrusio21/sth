# Copyright (c) 2026, DAS and contributors
# See license.txt

from datetime import date

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from sth.accounting_sth.doctype.perhitungan_kud.perhitungan_kud import (
	BARIS_JURNAL,
	BKM_BIAYA,
	KUNCI_BIAYA,
	KUNCI_LAIN_LAIN,
	ringkas_per_akun,
	cari_masa,
	hitung_shu,
	jenis_bkm,
	kelompokkan_netto,
	normalisasi_tahun_tanam,
	pecah_netto_tiket,
	baris_jurnal_biaya,
	rekap_biaya_bkm,
	susun_baris_jurnal,
	susun_belum_buku_besar,
	gabung_pembalikan,
	pembalikan_dari_rencana,
	KETERANGAN_DI_MUKA,
	KETERANGAN_MATERIAL,
	KETERANGAN_SELISIH,
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
				"biaya_bapp": 0.0,
			},
		)

	def test_bapp_dipisah_dari_bkm(self):
		baris = [
			baris_bkm("Buku Kerja Mandor Panen", 20.0),
			baris_bkm("BAPP", 7.5, jenis="BAPP", divisi=None),
		]

		rekap = rekap_biaya_bkm(baris)
		self.assertEqual(rekap["biaya_bapp"], 7.5)
		self.assertEqual(rekap["biaya_bkm_panen"], 20.0)

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

	def test_bapp_masuk_total_bukan_biaya_perawatan(self):
		doc = self.doc(
			[
				baris_bkm("Buku Kerja Mandor Perawatan", 10.0),
				baris_bkm("BAPP", 6.0, jenis="BAPP", divisi=None),
			],
			rincian_lain_lain=[{"akun": "AKUN-LAIN", "jumlah": 4.0}],
		)
		doc.hitung_biaya()

		self.assertEqual(doc.biaya_bapp, 6.0)
		self.assertEqual(doc.biaya_perawatan, 10.0)
		self.assertEqual(doc.total_biaya_perawatan_panen_dan_transport, 20.0)

	def test_lain_lain_masuk_lewat_total(self):
		doc = self.doc(
			[baris_bkm("Buku Kerja Mandor Perawatan", 10.0)],
			rincian_lain_lain=[{"akun": "AKUN-A", "jumlah": 4.0}, {"akun": "AKUN-B", "jumlah": 1.5}],
		)
		doc.hitung_biaya()

		self.assertEqual(doc.lain_lain, 5.5)
		self.assertEqual(doc.total_biaya_perawatan_panen_dan_transport, 15.5)

	def test_lain_lain_ketikan_ditimpa_jumlah_rincian(self):
		# Field Lain Lain cuma jumlah tabelnya; angka lepas tanpa baris tidak berlaku.
		doc = self.doc([baris_bkm("Buku Kerja Mandor Perawatan", 10.0)], lain_lain=999.0)
		doc.hitung_biaya()

		self.assertEqual(doc.lain_lain, 0.0)
		self.assertEqual(doc.total_biaya_perawatan_panen_dan_transport, 10.0)

	def test_lain_lain_ikut_terpotong_di_biaya_operasional(self):
		# Kalau lain-lain tidak sampai ke hitung_shu, angkanya cuma hiasan.
		doc = self.doc(
			[baris_bkm("Buku Kerja Mandor Perawatan", 1000.0)],
			rincian_lain_lain=[{"akun": "AKUN-LAIN", "jumlah": 250.0}],
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


# Peta akun sekadar penanda, bukan nama akun sungguhan — susun_baris_jurnal
# hanya meneruskan apa yang diberikan.
AKUN_JURNAL = {
	kunci: f"AKUN-{kunci}" for kunci, *_ in BARIS_JURNAL if kunci not in (KUNCI_BIAYA, KUNCI_LAIN_LAIN)
}

# Biaya yang seluruhnya sudah masuk buku besar, satu akun satu cost center.
def biaya_posted(jumlah):
	return [{"account": "AKUN-BIAYA", "cost_center": "CC-1", "jumlah": jumlah}] if jumlah else []

# Dua baris yang harus pasti kredit, dan field nilainya di dokumen.
MITRA_FIELD = {
	"akun_piutang_plasma": "angsuran_hutang",
	"akun_hutang_plasma_antara": "pembayaran_ke_mitra",
}


class TestSusunBarisJurnal(FrappeTestCase):
	"""Susunan jurnal dari Jurnal KUD.xlsx: satu debit, lima kredit."""

	# Angka Excel apa adanya. Management Fee di sana dibulatkan ke rupiah penuh
	# (1.961.474) sedangkan di sini 2 desimal, jadi beda ~0,2 rupiah — sengaja,
	# lihat catatan PRESISI_UANG.
	JUMLAH_PRODUKSI = 78458951.0
	BIAYA = 31654532.0

	def nilai(self, **kwargs):
		dasar = {
			"jumlah_produksi": self.JUMLAH_PRODUKSI,
			"total_biaya_perawatan_panen_dan_transport": self.BIAYA,
		}
		dasar.update(
			hitung_shu(
				dasar["jumlah_produksi"],
				dasar["total_biaya_perawatan_panen_dan_transport"],
				2.5,
				0.25,
				50,
			)
		)
		dasar.update(kwargs)
		return dasar

	def test_urutan_dan_sisi_sesuai_excel(self):
		baris = susun_baris_jurnal(self.nilai(), AKUN_JURNAL, biaya_posted(self.BIAYA))

		self.assertEqual(len(baris), 6)
		self.assertEqual(baris[0]["kunci"], "akun_pembelian_tbs")
		self.assertEqual(baris[0]["debit"], self.JUMLAH_PRODUKSI)
		self.assertEqual(baris[0]["credit"], 0)

		for row in baris[1:]:
			self.assertEqual(row["debit"], 0, msg=row["kunci"])
			self.assertGreater(row["credit"], 0, msg=row["kunci"])

	def test_akun_diambil_dari_peta(self):
		baris = susun_baris_jurnal(self.nilai(), AKUN_JURNAL, biaya_posted(self.BIAYA))
		lain = [row for row in baris if row["kunci"] != KUNCI_BIAYA]
		self.assertEqual(
			[row["account"] for row in lain],
			[AKUN_JURNAL[row["kunci"]] for row in lain],
		)

	def test_debit_dan_kredit_seimbang_tanpa_baris_pembulatan(self):
		# Inilah alasan hitung_shu() memakai sisa, bukan hitung ulang: kalau
		# Pembayaran ke Mitra dihitung sebagai persentase sendiri, jurnal ini
		# akan meleset satu sen dan butuh baris pembulatan.
		for persen_bagi_hasil in (50, 33.33, 66.67, 0, 100):
			nilai = {
				"jumlah_produksi": self.JUMLAH_PRODUKSI,
				"total_biaya_perawatan_panen_dan_transport": self.BIAYA,
			}
			nilai.update(
				hitung_shu(
					nilai["jumlah_produksi"],
					nilai["total_biaya_perawatan_panen_dan_transport"],
					2.5,
					0.25,
					persen_bagi_hasil,
				)
			)
			baris = susun_baris_jurnal(nilai, AKUN_JURNAL, biaya_posted(self.BIAYA))

			self.assertEqual(
				flt(sum(row["debit"] for row in baris), 2),
				flt(sum(row["credit"] for row in baris), 2),
				msg=f"persen_bagi_hasil={persen_bagi_hasil}",
			)

	def test_baris_nol_dibuang(self):
		# Mitra tanpa biaya BKM bulan itu, dan bagi hasil 100% ke angsuran.
		nilai = self.nilai(total_biaya_perawatan_panen_dan_transport=0, pembayaran_ke_mitra=0)
		kunci = [row["kunci"] for row in susun_baris_jurnal(nilai, AKUN_JURNAL)]

		self.assertNotIn(KUNCI_BIAYA, kunci)
		self.assertNotIn("akun_hutang_plasma_antara", kunci)
		self.assertIn("akun_pembelian_tbs", kunci)

	def test_nilai_negatif_tetap_kredit_bukan_pindah_ke_debit(self):
		# Biaya melampaui produksi: Hasil Bersih negatif, tapi Angsuran dan
		# Pembayaran tetap kredit — dicatat nilai mutlaknya, karena GL Entry
		# menolak angka minus dan sisi baris tidak boleh ikut tandanya.
		nilai = {
			"jumlah_produksi": self.JUMLAH_PRODUKSI,
			"total_biaya_perawatan_panen_dan_transport": 100000000.0,
		}
		nilai.update(hitung_shu(nilai["jumlah_produksi"], 100000000.0, 2.5, 0.25, 50))
		self.assertLess(nilai["hasil_bersih"], 0)

		baris = susun_baris_jurnal(nilai, AKUN_JURNAL, biaya_posted(100000000.0))

		for row in baris:
			self.assertGreaterEqual(row["debit"], 0, msg=row["kunci"])
			self.assertGreaterEqual(row["credit"], 0, msg=row["kunci"])

		for kunci in ("akun_piutang_plasma", "akun_hutang_plasma_antara"):
			mitra = [row for row in baris if row["kunci"] == kunci]
			self.assertTrue(mitra, msg=kunci)
			self.assertEqual(mitra[0]["debit"], 0, msg=kunci)
			self.assertEqual(mitra[0]["credit"], abs(nilai[MITRA_FIELD[kunci]]), msg=kunci)

		self.assertEqual(
			flt(sum(row["debit"] for row in baris), 2),
			flt(sum(row["credit"] for row in baris), 2),
		)

	def test_penutup_menanggung_selisih_bukan_jumlah_produksi(self):
		# Konsekuensi yang dipilih: di bulan minus, Pembelian TBS terdebit lebih
		# besar dari nilai TBS yang sungguh dibeli, sebesar dua kali Hasil Bersih.
		nilai = {
			"jumlah_produksi": self.JUMLAH_PRODUKSI,
			"total_biaya_perawatan_panen_dan_transport": 100000000.0,
		}
		nilai.update(hitung_shu(nilai["jumlah_produksi"], 100000000.0, 2.5, 0.25, 50))
		baris = susun_baris_jurnal(nilai, AKUN_JURNAL, biaya_posted(100000000.0))

		self.assertEqual(baris[0]["kunci"], "akun_pembelian_tbs")
		self.assertEqual(
			baris[0]["debit"],
			flt(self.JUMLAH_PRODUKSI - 2 * nilai["hasil_bersih"], 2),
		)

	def test_produksi_nol_tetap_memakai_akun_pembelian_tbs(self):
		# Dokumen yang produksinya belum ditarik tapi biayanya sudah masuk. Dulu
		# baris debitnya hilang sama sekali karena jumlah_produksi nol, lalu kedua
		# baris mitra mendarat di debit sebagai gantinya.
		biaya = 40595964.30
		nilai = {"jumlah_produksi": 0, "total_biaya_perawatan_panen_dan_transport": biaya}
		nilai.update(hitung_shu(0, biaya, 3, 0.5, 50))
		baris = susun_baris_jurnal(nilai, AKUN_JURNAL, biaya_posted(biaya))

		self.assertEqual(baris[0]["kunci"], "akun_pembelian_tbs")
		self.assertEqual(baris[0]["debit"], flt(2 * biaya, 2))
		self.assertEqual(
			flt(sum(row["debit"] for row in baris), 2),
			flt(sum(row["credit"] for row in baris), 2),
		)

	def test_dokumen_kosong_tidak_menghasilkan_baris(self):
		self.assertEqual(susun_baris_jurnal({}, AKUN_JURNAL), [])

	def test_biaya_belum_posted_tidak_dijurnal_penutup_mengecil(self):
		# Keadaan sebenarnya: BKM TMDE Juli 2026, dari 37.595.964,30 yang ditagih
		# baru 11.918.879,86 yang GL-nya lahir. Sisanya tidak punya baris, dan
		# Pembelian TBS terdebit lebih kecil sebesar itu. Mitra tetap ditagih penuh.
		biaya, posted = 37595964.30, 11918879.86
		nilai = {"jumlah_produksi": self.JUMLAH_PRODUKSI, "total_biaya_perawatan_panen_dan_transport": biaya}
		nilai.update(hitung_shu(self.JUMLAH_PRODUKSI, biaya, 2.5, 0.25, 50))
		baris = susun_baris_jurnal(nilai, AKUN_JURNAL, biaya_posted(posted))

		biaya_rows = [row for row in baris if row["kunci"] == KUNCI_BIAYA]
		self.assertEqual(len(biaya_rows), 1)
		self.assertEqual(biaya_rows[0]["credit"], posted)
		self.assertEqual(baris[0]["debit"], flt(self.JUMLAH_PRODUKSI - (biaya - posted), 2))
		self.assertEqual(
			flt(sum(row["debit"] for row in baris), 2),
			flt(sum(row["credit"] for row in baris), 2),
		)

	def test_tanpa_bkm_posted_tidak_ada_baris_biaya(self):
		baris = susun_baris_jurnal(self.nilai(), AKUN_JURNAL)

		self.assertNotIn(KUNCI_BIAYA, [row["kunci"] for row in baris])
		self.assertEqual(baris[0]["debit"], flt(self.JUMLAH_PRODUKSI - self.BIAYA, 2))

	def nilai_lain_lain(self, *rincian):
		# Lain Lain bagian dari Total Biaya; biaya BKM-nya sendiri sudah Posted semua.
		# Tiap rincian (jumlah) atau (jumlah, akun, cost_center, keterangan).
		rincian = [
			dict(zip(("jumlah", "akun", "cost_center", "keterangan"), r if isinstance(r, tuple) else (r, "AKUN-LAIN")))
			for r in rincian
		]
		lain_lain = sum(row["jumlah"] for row in rincian)
		total = self.BIAYA + lain_lain
		nilai = {
			"jumlah_produksi": self.JUMLAH_PRODUKSI,
			"total_biaya_perawatan_panen_dan_transport": total,
			"lain_lain": lain_lain,
			"rincian_lain_lain": rincian,
		}
		nilai.update(hitung_shu(self.JUMLAH_PRODUKSI, total, 2.5, 0.25, 50))
		return nilai

	def test_lain_lain_dikredit_penutup_kembali_jumlah_produksi(self):
		baris = susun_baris_jurnal(self.nilai_lain_lain(3000000.0), AKUN_JURNAL, biaya_posted(self.BIAYA))

		lain = [row for row in baris if row["kunci"] == KUNCI_LAIN_LAIN]
		self.assertEqual(len(lain), 1)
		self.assertEqual(lain[0]["account"], "AKUN-LAIN")
		self.assertEqual((lain[0]["debit"], lain[0]["credit"]), (0.0, 3000000.0))
		self.assertEqual(baris[0]["debit"], self.JUMLAH_PRODUKSI)

	def test_lain_lain_satu_baris_jurnal_per_rincian(self):
		baris = susun_baris_jurnal(
			self.nilai_lain_lain(
				(2000000.0, "AKUN-A", "CC-1", "Potongan pupuk"),
				(1000000.0, "AKUN-B", None, None),
				(0.0, "AKUN-C", None, "Nol tidak jadi baris"),
			),
			AKUN_JURNAL,
			biaya_posted(self.BIAYA),
		)

		lain = [row for row in baris if row["kunci"] == KUNCI_LAIN_LAIN]
		self.assertEqual(
			[(row["account"], row["cost_center"], row["credit"], row["keterangan"]) for row in lain],
			[
				("AKUN-A", "CC-1", 2000000.0, "Lain Lain: Potongan pupuk"),
				("AKUN-B", None, 1000000.0, "Lain Lain"),
			],
		)
		self.assertEqual(baris[0]["debit"], self.JUMLAH_PRODUKSI)

	def test_lain_lain_campur_tanda_tetap_seimbang(self):
		baris = susun_baris_jurnal(
			self.nilai_lain_lain((750000.0, "AKUN-A", None, None), (-250000.0, "AKUN-B", None, None)),
			AKUN_JURNAL,
			biaya_posted(self.BIAYA),
		)

		lain = {row["account"]: (row["debit"], row["credit"]) for row in baris if row["kunci"] == KUNCI_LAIN_LAIN}
		self.assertEqual(lain, {"AKUN-A": (0.0, 750000.0), "AKUN-B": (250000.0, 0.0)})
		self.assertEqual(baris[0]["debit"], self.JUMLAH_PRODUKSI)
		self.assertEqual(
			flt(sum(row["debit"] for row in baris), 2),
			flt(sum(row["credit"] for row in baris), 2),
		)

	def test_lain_lain_minus_pindah_ke_debit(self):
		baris = susun_baris_jurnal(self.nilai_lain_lain(-500000.0), AKUN_JURNAL, biaya_posted(self.BIAYA))

		lain = [row for row in baris if row["kunci"] == KUNCI_LAIN_LAIN]
		self.assertEqual((lain[0]["debit"], lain[0]["credit"]), (500000.0, 0.0))
		self.assertEqual(baris[0]["debit"], self.JUMLAH_PRODUKSI)
		self.assertEqual(
			flt(sum(row["debit"] for row in baris), 2),
			flt(sum(row["credit"] for row in baris), 2),
		)


class TestBarisJurnalBiaya(FrappeTestCase):
	"""Baris biaya: tiap akun di bawah Kepala Akun Biaya dinolkan, tanpa akun kontra."""

	def pembalikan(self, *jumlah):
		return [
			{"account": f"AKUN-BIAYA-{i}", "cost_center": f"CC-{i}", "jumlah": n}
			for i, n in enumerate(jumlah, start=1)
		]

	def test_tanpa_pembalikan_tidak_ada_baris(self):
		# BKM-nya belum ada yang Posted: tidak ada yang dijurnal.
		self.assertEqual(baris_jurnal_biaya(None), [])
		self.assertEqual(baris_jurnal_biaya([]), [])

	def test_satu_baris_per_akun_dan_cost_center(self):
		baris = baris_jurnal_biaya(self.pembalikan(28594222.76, 9001741.54))

		self.assertEqual(len(baris), 2)
		self.assertEqual([row["account"] for row in baris], ["AKUN-BIAYA-1", "AKUN-BIAYA-2"])
		self.assertEqual([row["cost_center"] for row in baris], ["CC-1", "CC-2"])
		self.assertEqual([row["credit"] for row in baris], [28594222.76, 9001741.54])
		self.assertTrue(all(row["kunci"] == KUNCI_BIAYA for row in baris))

	def test_saldo_kredit_di_akun_biaya_jadi_debit(self):
		baris = baris_jurnal_biaya(self.pembalikan(-500000.0))

		self.assertEqual(baris[0]["debit"], 500000.0)
		self.assertEqual(baris[0]["credit"], 0)

	def test_pembalikan_nol_dilewati(self):
		self.assertEqual(baris_jurnal_biaya(self.pembalikan(0, 0)), [])


class TestSusunBelumBukuBesar(FrappeTestCase):
	"""Rincian biaya yang tidak dijurnal, per akun tujuan."""

	PANEN = "Buku Kerja Mandor Panen"
	RAWAT = "Buku Kerja Mandor Perawatan"

	def test_bkm_belum_posted_ke_akun_kegiatan(self):
		baris = [baris_bkm(self.PANEN, 100.0, voucher_no="P1")]
		rencana = {(self.PANEN, "P1"): {"status": "Submitted", "bagian": [("6110 - PANEN", None, 100.0, "CC-P")]}}

		hasil = susun_belum_buku_besar(baris, {}, rencana)

		self.assertEqual(len(hasil), 1)
		self.assertEqual(hasil[0]["akun"], "6110 - PANEN")
		self.assertEqual(hasil[0]["belum"], 100.0)
		self.assertEqual(hasil[0]["sudah_buku_besar"], 0.0)

	def test_bkm_posted_tidak_muncul(self):
		baris = [baris_bkm(self.PANEN, 100.0, voucher_no="P1")]
		rencana = {(self.PANEN, "P1"): {"status": "Posted", "bagian": [("6110 - PANEN", None, 100.0, "CC-P")]}}

		self.assertEqual(susun_belum_buku_besar(baris, {(self.PANEN, "P1"): 100.0}, rencana), [])

	def test_perawatan_posted_sisa_material(self):
		# Upah + premi sudah di GL, material tidak pernah lewat GL BKM.
		baris = [baris_bkm(self.RAWAT, 150.0, voucher_no="R1")]
		rencana = {(self.RAWAT, "R1"): {"status": "Posted", "bagian": [
			("6210 - RAWAT", None, 100.0, "CC-R"),
			(None, KETERANGAN_MATERIAL, 50.0, None),
		]}}

		hasil = susun_belum_buku_besar(baris, {(self.RAWAT, "R1"): 100.0}, rencana)

		self.assertEqual([(r["akun"], r["keterangan"], r["belum"]) for r in hasil],
			[(None, KETERANGAN_MATERIAL, 50.0)])

	def test_perawatan_belum_posted_dipecah_dua(self):
		baris = [baris_bkm(self.RAWAT, 150.0, voucher_no="R1")]
		rencana = {(self.RAWAT, "R1"): {"status": "Submitted", "bagian": [
			("6210 - RAWAT", None, 100.0, "CC-R"),
			(None, KETERANGAN_MATERIAL, 50.0, None),
		]}}

		hasil = susun_belum_buku_besar(baris, {}, rencana)

		self.assertEqual([(r["akun"], r["belum"]) for r in hasil], [("6210 - RAWAT", 100.0), (None, 50.0)])

	def test_sisa_tak_terjelaskan_jadi_selisih(self):
		# Lain Lain tidak lagi di sini: barisnya sendiri di jurnal.
		baris = [baris_bkm("BAPP", 90.0, voucher_no="B1", jenis="BAPP")]

		hasil = susun_belum_buku_besar(baris, {("BAPP", "B1"): 80.0}, {})

		self.assertEqual([(r["keterangan"], r["belum"], r["dijurnal"]) for r in hasil],
			[(KETERANGAN_SELISIH, 10.0, 0)])

	def test_total_sama_dengan_status_jurnal(self):
		# Status jurnal: Total Biaya - saldo yang dinolkan.
		baris = [
			baris_bkm(self.PANEN, 100.0, voucher_no="P1"),
			baris_bkm(self.PANEN, 200.0, voucher_no="P2"),
			baris_bkm(self.RAWAT, 150.0, voucher_no="R1"),
		]
		gl = {(self.PANEN, "P2"): 200.0, (self.RAWAT, "R1"): 100.0}
		rencana = {
			(self.PANEN, "P1"): {"bagian": [("A", None, 100.0, "CC-A")]},
			(self.PANEN, "P2"): {"bagian": [("A", None, 200.0, "CC-A")]},
			(self.RAWAT, "R1"): {"bagian": [("B", None, 100.0, "CC-B"), (None, KETERANGAN_MATERIAL, 50.0, None)]},
		}
		hasil = susun_belum_buku_besar(baris, gl, rencana)

		total_biaya = sum(r["nilai"] for r in baris)
		self.assertEqual(sum(r["belum"] for r in hasil), total_biaya - sum(gl.values()))

	def test_belum_posted_di_bawah_kepala_dijurnal_di_muka(self):
		baris = [baris_bkm(self.PANEN, 100.0, voucher_no="P1")]
		rencana = {(self.PANEN, "P1"): {"status": "Submitted", "bagian": [("6110 - PANEN", None, 100.0, "CC-P")]}}

		# Tetap tampil di rincian, dengan tanda ikut dijurnal.
		hasil = susun_belum_buku_besar(baris, {}, rencana, {"6110 - PANEN"})

		self.assertEqual([(r["akun"], r["cost_center"], r["belum"], r["dijurnal"]) for r in hasil],
			[("6110 - PANEN", "CC-P", 100.0, 1)])
		self.assertEqual(pembalikan_dari_rencana(baris, {}, rencana, {"6110 - PANEN"}), [
			{"account": "6110 - PANEN", "cost_center": "CC-P", "jumlah": 100.0, "keterangan": KETERANGAN_DI_MUKA},
		])

	def test_belum_posted_di_luar_kepala_tetap_belum(self):
		baris = [baris_bkm(self.PANEN, 100.0, voucher_no="P1")]
		rencana = {(self.PANEN, "P1"): {"status": "Submitted", "bagian": [("1262201 - TBM", None, 100.0, "CC-P")]}}

		hasil = susun_belum_buku_besar(baris, {}, rencana, {"6110 - PANEN"})

		self.assertEqual([(r["akun"], r["belum"], r["dijurnal"]) for r in hasil], [("1262201 - TBM", 100.0, 0)])

	def test_tanpa_cost_center_tidak_dijurnal_di_muka(self):
		# BKM Perawatan tanpa cost center tidak pernah dibuatkan GL.
		baris = [baris_bkm(self.RAWAT, 100.0, voucher_no="R1")]
		rencana = {(self.RAWAT, "R1"): {"status": "Submitted", "bagian": [("6210 - RAWAT", None, 100.0, "")]}}

		hasil = susun_belum_buku_besar(baris, {}, rencana, {"6210 - RAWAT"})

		self.assertEqual([(r["belum"], r["dijurnal"]) for r in hasil], [(100.0, 0)])
		self.assertEqual(pembalikan_dari_rencana(baris, {}, rencana, {"6210 - RAWAT"}), [])

	def test_perawatan_belum_posted_upah_dijurnal_material_tetap_belum(self):
		baris = [baris_bkm(self.RAWAT, 150.0, voucher_no="R1")]
		rencana = {(self.RAWAT, "R1"): {"status": "Submitted", "bagian": [
			("6210 - RAWAT", None, 100.0, "CC-R"),
			(None, KETERANGAN_MATERIAL, 50.0, None),
		]}}

		hasil = susun_belum_buku_besar(baris, {}, rencana, {"6210 - RAWAT"})

		self.assertEqual([(r["akun"], r["keterangan"], r["belum"], r["dijurnal"]) for r in hasil],
			[("6210 - RAWAT", None, 100.0, 1), (None, KETERANGAN_MATERIAL, 50.0, 0)])
		self.assertEqual(pembalikan_dari_rencana(baris, {}, rencana, {"6210 - RAWAT"}),
			[{"account": "6210 - RAWAT", "cost_center": "CC-R", "jumlah": 100.0, "keterangan": KETERANGAN_DI_MUKA}])

	def test_sudah_ada_gl_tidak_dijurnal_dua_kali(self):
		baris = [baris_bkm(self.PANEN, 100.0, voucher_no="P1")]
		rencana = {(self.PANEN, "P1"): {"status": "Posted", "bagian": [("6110 - PANEN", None, 100.0, "CC-P")]}}

		self.assertEqual(pembalikan_dari_rencana(baris, {(self.PANEN, "P1"): 100.0}, rencana, {"6110 - PANEN"}), [])

	def test_total_sama_dengan_status_jurnal_dengan_jurnal_di_muka(self):
		baris = [
			baris_bkm(self.PANEN, 100.0, voucher_no="P1"),
			baris_bkm(self.PANEN, 200.0, voucher_no="P2"),
			baris_bkm(self.RAWAT, 150.0, voucher_no="R1"),
			baris_bkm(self.RAWAT, 70.0, voucher_no="R2"),
		]
		gl = {(self.PANEN, "P2"): 200.0}
		rencana = {
			(self.PANEN, "P1"): {"bagian": [("A", None, 100.0, "CC-A")]},
			(self.PANEN, "P2"): {"bagian": [("A", None, 200.0, "CC-A")]},
			(self.RAWAT, "R1"): {"bagian": [("B", None, 100.0, "CC-B"), (None, KETERANGAN_MATERIAL, 50.0, None)]},
			(self.RAWAT, "R2"): {"bagian": [("LUAR", None, 70.0, "CC-B")]},
		}
		akun = {"A", "B"}
		gl_pembalikan = [{"account": "A", "cost_center": "CC-A", "jumlah": 200.0}]

		pembalikan = gabung_pembalikan(gl_pembalikan, pembalikan_dari_rencana(baris, gl, rencana, akun))
		hasil = susun_belum_buku_besar(baris, gl, rencana, akun)

		# GL yang ada dan yang di muka tetap dua baris walau akun & cost center sama.
		self.assertEqual(pembalikan, [
			{"account": "A", "cost_center": "CC-A", "jumlah": 200.0, "keterangan": None},
			{"account": "A", "cost_center": "CC-A", "jumlah": 100.0, "keterangan": KETERANGAN_DI_MUKA},
			{"account": "B", "cost_center": "CC-B", "jumlah": 100.0, "keterangan": KETERANGAN_DI_MUKA},
		])
		total_biaya = sum(r["nilai"] for r in baris)
		tidak_dijurnal = sum(r["belum"] for r in hasil if not r["dijurnal"])
		self.assertEqual(tidak_dijurnal, total_biaya - sum(r["jumlah"] for r in pembalikan))
		self.assertEqual(sum(r["belum"] for r in hasil if r["dijurnal"]), 200.0)


class TestRingkasPerAkun(FrappeTestCase):
	"""Pratinjau jurnal: baris biaya satu per akun, cost center baru dipecah di GL Entry."""

	def test_cost_center_digabung_per_akun_dan_keterangan(self):
		pembalikan = [
			{"account": "A", "cost_center": "CC-1", "jumlah": 100.0, "keterangan": KETERANGAN_DI_MUKA},
			{"account": "A", "cost_center": "CC-2", "jumlah": 50.0, "keterangan": KETERANGAN_DI_MUKA},
			{"account": "A", "cost_center": "CC-1", "jumlah": 30.0},
			{"account": "B", "cost_center": "CC-1", "jumlah": 20.0, "keterangan": KETERANGAN_DI_MUKA},
		]
		baris = susun_baris_jurnal({"jumlah_produksi": 1000.0}, AKUN_JURNAL, pembalikan)

		ringkas = ringkas_per_akun(baris)
		biaya = [(r["account"], r["keterangan"], r["cost_center"], r["credit"]) for r in ringkas if r["kunci"] == KUNCI_BIAYA]

		self.assertEqual(biaya, [
			("A", KETERANGAN_DI_MUKA, None, 150.0),
			("A", "Nol-kan biaya A", None, 30.0),
			("B", KETERANGAN_DI_MUKA, None, 20.0),
		])
		self.assertEqual(sum(r["debit"] for r in ringkas), sum(r["debit"] for r in baris))
		self.assertEqual(sum(r["credit"] for r in ringkas), sum(r["credit"] for r in baris))

	def test_dua_sisi_dinetto(self):
		pembalikan = [
			{"account": "A", "cost_center": "CC-1", "jumlah": 100.0},
			{"account": "A", "cost_center": "CC-2", "jumlah": -40.0},
		]
		baris = susun_baris_jurnal({}, AKUN_JURNAL, pembalikan)

		biaya = [r for r in ringkas_per_akun(baris) if r["kunci"] == KUNCI_BIAYA]

		self.assertEqual([(r["debit"], r["credit"]) for r in biaya], [(0.0, 60.0)])
