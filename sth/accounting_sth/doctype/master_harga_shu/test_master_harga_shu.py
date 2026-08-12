# Copyright (c) 2026, DAS and contributors
# See license.txt

from datetime import date

from frappe.tests.utils import FrappeTestCase

from sth.accounting_sth.doctype.master_harga_shu.master_harga_shu import (
	bagi_rata_masa,
	check_baris_terkunci,
	check_harga_rows,
	check_masa_rows,
	check_masa_setahun,
	check_masa_terkunci,
	kelompok_untuk_umur,
	rentang_bulan,
)

JAN_MULAI = date(2026, 1, 1)
JAN_SELESAI = date(2026, 1, 31)

BULAN_INDO = (
	"Januari",
	"Februari",
	"Maret",
	"April",
	"Mei",
	"Juni",
	"Juli",
	"Agustus",
	"September",
	"Oktober",
	"November",
	"Desember",
)

# Pembagian sungguhan Januari 2026, disalin dari file Excel SHU yang dipakai
# sekarang. Ini yang harus lolos apa adanya.
JANUARI_2026 = [
	(1, date(2026, 1, 1), date(2026, 1, 2)),
	(2, date(2026, 1, 3), date(2026, 1, 8)),
	(3, date(2026, 1, 9), date(2026, 1, 15)),
	(4, date(2026, 1, 16), date(2026, 1, 22)),
	(5, date(2026, 1, 23), date(2026, 1, 29)),
	(6, date(2026, 1, 30), date(2026, 1, 31)),
]


def buat(baris):
	return [
		{"masa_no": no, "tanggal_mulai": mulai, "tanggal_selesai": selesai}
		for no, mulai, selesai in baris
	]


def masa(bulan_no, baris):
	return [dict(row, bulan_no=bulan_no) for row in buat(baris)]


def harga(*spec):
	"""spec: (bulan_no, masa_no, kelompok_umur, harga)"""
	return [
		{"bulan_no": b, "masa_no": m, "kelompok_umur": k, "harga": h} for b, m, k, h in spec
	]


class TestCheckMasaRows(FrappeTestCase):
	def test_pembagian_januari_2026_asli_lolos(self):
		self.assertEqual(check_masa_rows(buat(JANUARI_2026), JAN_MULAI, JAN_SELESAI), [])

	def test_satu_masa_sebulan_penuh_lolos(self):
		rows = buat([(1, JAN_MULAI, JAN_SELESAI)])
		self.assertEqual(check_masa_rows(rows, JAN_MULAI, JAN_SELESAI), [])

	def test_tiap_hari_jadi_satu_masa_lolos(self):
		baris = [(i, date(2026, 1, i), date(2026, 1, i)) for i in range(1, 32)]
		self.assertEqual(check_masa_rows(buat(baris), JAN_MULAI, JAN_SELESAI), [])

	def test_jumlah_masa_bebas_tidak_ada_pola_yang_dipaksakan(self):
		# Aturan yang sama harus menerima 3, 6, maupun 8 masa.
		for jumlah in (3, 6, 8):
			rows = bagi_rata_masa(JAN_MULAI, JAN_SELESAI, jumlah)
			with self.subTest(jumlah=jumlah):
				self.assertEqual(check_masa_rows(rows, JAN_MULAI, JAN_SELESAI), [])

	def test_tolak_kalau_tidak_ada_masa(self):
		errors = check_masa_rows([], JAN_MULAI, JAN_SELESAI)
		self.assertEqual(len(errors), 1)
		self.assertIn("Minimal", errors[0])

	def test_tolak_nomor_masa_tidak_berurutan(self):
		rows = buat([(1, date(2026, 1, 1), date(2026, 1, 15)), (3, date(2026, 1, 16), JAN_SELESAI)])
		errors = check_masa_rows(rows, JAN_MULAI, JAN_SELESAI)
		self.assertTrue(any("bernomor 2" in e for e in errors))

	def test_tolak_tanggal_selesai_mendahului_mulai(self):
		rows = buat([(1, date(2026, 1, 15), date(2026, 1, 3))])
		errors = check_masa_rows(rows, JAN_MULAI, JAN_SELESAI)
		self.assertTrue(any("mendahului" in e for e in errors))

	def test_tolak_tanggal_kosong(self):
		rows = [{"masa_no": 1, "tanggal_mulai": None, "tanggal_selesai": None}]
		errors = check_masa_rows(rows, JAN_MULAI, JAN_SELESAI)
		self.assertTrue(any("wajib diisi" in e for e in errors))

	def test_tolak_tidak_mulai_awal_bulan(self):
		rows = buat([(1, date(2026, 1, 2), JAN_SELESAI)])
		errors = check_masa_rows(rows, JAN_MULAI, JAN_SELESAI)
		self.assertTrue(any("awal bulan" in e for e in errors))

	def test_tolak_tidak_selesai_akhir_bulan(self):
		rows = buat([(1, JAN_MULAI, date(2026, 1, 30))])
		errors = check_masa_rows(rows, JAN_MULAI, JAN_SELESAI)
		self.assertTrue(any("akhir bulan" in e for e in errors))

	def test_tolak_ada_celah(self):
		# 16 Januari tidak tercakup masa manapun.
		rows = buat(
			[
				(1, date(2026, 1, 1), date(2026, 1, 15)),
				(2, date(2026, 1, 17), JAN_SELESAI),
			]
		)
		errors = check_masa_rows(rows, JAN_MULAI, JAN_SELESAI)
		self.assertTrue(any("celah" in e for e in errors))
		self.assertTrue(any("2026-01-16" in e for e in errors))

	def test_tolak_tumpang_tindih(self):
		# 15 Januari masuk dua masa sekaligus.
		rows = buat(
			[
				(1, date(2026, 1, 1), date(2026, 1, 15)),
				(2, date(2026, 1, 15), JAN_SELESAI),
			]
		)
		errors = check_masa_rows(rows, JAN_MULAI, JAN_SELESAI)
		self.assertTrue(any("tumpang tindih" in e for e in errors))

	def test_tolak_tanggal_di_luar_bulan(self):
		rows = buat([(1, JAN_MULAI, date(2026, 2, 5))])
		errors = check_masa_rows(rows, JAN_MULAI, JAN_SELESAI)
		self.assertTrue(any("di luar bulan" in e for e in errors))

	def test_baris_cacat_tidak_memicu_pesan_celah_yang_membingungkan(self):
		rows = buat([(1, JAN_MULAI, None), (2, date(2026, 1, 10), JAN_SELESAI)])
		errors = check_masa_rows(rows, JAN_MULAI, JAN_SELESAI)
		self.assertTrue(any("wajib diisi" in e for e in errors))
		self.assertFalse(any("celah" in e for e in errors))

	def test_menerima_tanggal_berbentuk_string(self):
		rows = [
			{"masa_no": 1, "tanggal_mulai": "2026-01-01", "tanggal_selesai": "2026-01-15"},
			{"masa_no": 2, "tanggal_mulai": "2026-01-16", "tanggal_selesai": "2026-01-31"},
		]
		self.assertEqual(check_masa_rows(rows, "2026-01-01", "2026-01-31"), [])


class TestCheckMasaSetahun(FrappeTestCase):
	def test_tanpa_baris_sama_sekali_lolos(self):
		# Dokumen tahunan boleh dibuat sebelum masanya dibagi.
		self.assertEqual(check_masa_setahun([], 2026), [])

	def test_dua_bulan_terisi_penuh_lolos(self):
		rows = masa(1, JANUARI_2026) + masa(
			2, [(1, date(2026, 2, 1), date(2026, 2, 14)), (2, date(2026, 2, 15), date(2026, 2, 28))]
		)
		self.assertEqual(check_masa_setahun(rows, 2026), [])

	def test_bulan_yang_tidak_diisi_dilewat(self):
		# Januari penuh, sebelas bulan lain kosong — itu sah, bukan kesalahan.
		self.assertEqual(check_masa_setahun(masa(1, JANUARI_2026), 2026), [])

	def test_tolak_bulan_yang_terisi_setengah(self):
		rows = masa(1, JANUARI_2026) + masa(2, [(1, date(2026, 2, 1), date(2026, 2, 14))])
		errors = check_masa_setahun(rows, 2026)
		self.assertTrue(any("Februari" in e and "akhir bulan" in e for e in errors))
		self.assertFalse(any("Januari" in e for e in errors))

	def test_februari_tahun_kabisat_ikut_tahun_dokumen(self):
		rows = masa(2, [(1, date(2028, 2, 1), date(2028, 2, 29))])
		self.assertEqual(check_masa_setahun(rows, 2028), [])

	def test_tolak_baris_tanpa_bulan(self):
		rows = [{"masa_no": 1, "tanggal_mulai": JAN_MULAI, "tanggal_selesai": JAN_SELESAI}]
		errors = check_masa_setahun(rows, 2026)
		self.assertTrue(any("bulannya belum diisi" in e for e in errors))


class TestBagiRataMasa(FrappeTestCase):
	def test_hasilnya_selalu_lolos_validasi(self):
		# Tiap bulan 2026, tiap jumlah masa 1..10 — semuanya harus menutup penuh.
		for bulan_no in range(1, 13):
			awal, akhir = rentang_bulan(2026, BULAN_INDO[bulan_no - 1])
			for jumlah in range(1, 11):
				rows = bagi_rata_masa(awal, akhir, jumlah)
				with self.subTest(bulan=bulan_no, jumlah=jumlah):
					self.assertEqual(len(rows), jumlah)
					self.assertEqual(check_masa_rows(rows, awal, akhir), [])

	def test_sisa_hari_masuk_ke_masa_terdepan(self):
		# Januari 31 hari dibagi 6 -> 5 masa berisi 6 hari, 1 masa berisi 5 hari.
		rows = bagi_rata_masa(JAN_MULAI, JAN_SELESAI, 6)
		self.assertEqual([r["jumlah_hari"] for r in rows], [6, 5, 5, 5, 5, 5])
		self.assertEqual(sum(r["jumlah_hari"] for r in rows), 31)

	def test_februari_tahun_kabisat(self):
		awal, akhir = rentang_bulan(2028, "Februari")
		self.assertEqual(akhir, date(2028, 2, 29))
		rows = bagi_rata_masa(awal, akhir, 4)
		self.assertEqual([r["jumlah_hari"] for r in rows], [8, 7, 7, 7])
		self.assertEqual(check_masa_rows(rows, awal, akhir), [])

	def test_tolak_jumlah_masa_melebihi_jumlah_hari(self):
		from frappe.exceptions import ValidationError

		with self.assertRaises(ValidationError):
			bagi_rata_masa(JAN_MULAI, JAN_SELESAI, 32)

	def test_tolak_jumlah_masa_nol(self):
		from frappe.exceptions import ValidationError

		with self.assertRaises(ValidationError):
			bagi_rata_masa(JAN_MULAI, JAN_SELESAI, 0)


class TestRentangBulan(FrappeTestCase):
	def test_menerima_nama_maupun_nomor(self):
		self.assertEqual(rentang_bulan(2026, "Januari"), rentang_bulan(2026, 1))

	def test_tolak_bulan_yang_tidak_dikenal(self):
		from frappe.exceptions import ValidationError

		with self.assertRaises(ValidationError):
			rentang_bulan(2026, "Janwari")


class TestKelompokUmur(FrappeTestCase):
	def test_umur_muda_punya_kolom_sendiri_sendiri(self):
		for umur in range(3, 10):
			with self.subTest(umur=umur):
				self.assertEqual(kelompok_untuk_umur(umur)["label"], str(umur))

	def test_umur_10_sampai_20_jadi_satu_kelompok(self):
		# Ini inti perubahannya: umur 15 dan 16 dihargai sama.
		for umur in (10, 15, 16, 20):
			with self.subTest(umur=umur):
				self.assertEqual(kelompok_untuk_umur(umur)["label"], "10 - 20")

	def test_umur_21_sampai_24_jadi_satu_kelompok(self):
		for umur in (21, 24):
			with self.subTest(umur=umur):
				self.assertEqual(kelompok_untuk_umur(umur)["label"], "21 - 24")

	def test_lebih_tua_dari_25_ikut_kelompok_terakhir(self):
		# Kebun tua tetap terbayar, tidak jatuh ke harga 0.
		for umur in (25, 26, 40):
			with self.subTest(umur=umur):
				self.assertEqual(kelompok_untuk_umur(umur)["label"], "25")

	def test_di_bawah_3_tahun_tidak_punya_kelompok(self):
		for umur in (0, 1, 2):
			with self.subTest(umur=umur):
				self.assertIsNone(kelompok_untuk_umur(umur))

	def test_kelompok_tidak_saling_tumpang_tindih(self):
		for umur in range(3, 60):
			with self.subTest(umur=umur):
				self.assertIsNotNone(kelompok_untuk_umur(umur))


class TestCheckHargaRows(FrappeTestCase):
	def test_lolos(self):
		rows = harga((1, 1, "3", 3406.67), (1, 1, "10 - 20", 3406.67), (1, 2, "3", 3374.96))
		self.assertEqual(check_harga_rows(rows), [])

	def test_harga_nol_boleh(self):
		# Nol adalah harga yang sah. Yang berarti "belum ditetapkan" adalah
		# tidak adanya baris sama sekali.
		self.assertEqual(check_harga_rows(harga((1, 1, "3", 0))), [])

	def test_tolak_harga_negatif(self):
		errors = check_harga_rows(harga((1, 1, "3", -5)))
		self.assertTrue(any("negatif" in e for e in errors))

	def test_tolak_kelompok_umur_yang_tidak_dikenal(self):
		errors = check_harga_rows(harga((1, 1, "11 - 19", 3406.67)))
		self.assertTrue(any("tidak dikenali" in e for e in errors))

	def test_tolak_baris_ganda(self):
		rows = harga((1, 1, "10 - 20", 3406.67), (1, 1, "10 - 20", 3500))
		errors = check_harga_rows(rows)
		self.assertTrue(any("ganda" in e for e in errors))

	def test_masa_sama_kelompok_beda_bukan_ganda(self):
		rows = harga((1, 1, "10 - 20", 3406.67), (1, 1, "21 - 24", 3406.67))
		self.assertEqual(check_harga_rows(rows), [])

	def test_bulan_beda_masa_sama_bukan_ganda(self):
		rows = harga((1, 1, "3", 3406.67), (2, 1, "3", 3500))
		self.assertEqual(check_harga_rows(rows), [])


class TestCheckBarisTerkunci(FrappeTestCase):
	def setUp(self):
		self.lama = harga(
			(1, 1, "10 - 20", 3406.67), (1, 2, "10 - 20", 3374.96), (2, 1, "10 - 20", 3500)
		)

	def test_tanpa_bulan_terkunci_bebas(self):
		baru = harga((1, 1, "10 - 20", 9999))
		self.assertEqual(check_baris_terkunci(self.lama, baru, set()), [])

	def test_bulan_tidak_terkunci_bebas_diubah(self):
		# Januari terkunci, Februari tidak — ubah Februari harus boleh.
		baru = harga(
			(1, 1, "10 - 20", 3406.67), (1, 2, "10 - 20", 3374.96), (2, 1, "10 - 20", 9999)
		)
		self.assertEqual(check_baris_terkunci(self.lama, baru, {1}), [])

	def test_tolak_ubah_harga_di_bulan_terkunci(self):
		baru = harga(
			(1, 1, "10 - 20", 9999), (1, 2, "10 - 20", 3374.96), (2, 1, "10 - 20", 3500)
		)
		errors = check_baris_terkunci(self.lama, baru, {1})
		self.assertTrue(any("tidak boleh diubah" in e for e in errors))

	def test_tolak_hapus_baris_di_bulan_terkunci(self):
		baru = harga((1, 1, "10 - 20", 3406.67), (2, 1, "10 - 20", 3500))
		errors = check_baris_terkunci(self.lama, baru, {1})
		self.assertTrue(any("tidak boleh dihapus" in e for e in errors))

	def test_tolak_tambah_baris_di_bulan_terkunci(self):
		baru = self.lama + harga((1, 1, "21 - 24", 3406.67))
		errors = check_baris_terkunci(self.lama, baru, {1})
		self.assertTrue(any("tidak boleh menambah" in e for e in errors))

	def test_tidak_berubah_apa_apa_lolos(self):
		self.assertEqual(check_baris_terkunci(self.lama, list(self.lama), {1, 2}), [])

	def test_sel_kosong_di_bulan_terkunci_tetap_boleh_kosong(self):
		# Penetapan sebagian itu normal: kelompok 3 tidak pernah punya baris di
		# Januari, dan itu tidak boleh dianggap pelanggaran.
		errors = check_baris_terkunci(self.lama, list(self.lama), {1})
		self.assertEqual(errors, [])


class TestCheckMasaTerkunci(FrappeTestCase):
	def setUp(self):
		self.lama = masa(1, JANUARI_2026) + masa(
			2, [(1, date(2026, 2, 1), date(2026, 2, 28))]
		)

	def test_tanpa_bulan_terkunci_bebas(self):
		baru = masa(1, [(1, JAN_MULAI, JAN_SELESAI)])
		self.assertEqual(check_masa_terkunci(self.lama, baru, set()), [])

	def test_bulan_lain_bebas_digeser(self):
		baru = masa(1, JANUARI_2026) + masa(
			2, [(1, date(2026, 2, 1), date(2026, 2, 14)), (2, date(2026, 2, 15), date(2026, 2, 28))]
		)
		self.assertEqual(check_masa_terkunci(self.lama, baru, {1}), [])

	def test_tolak_geser_tanggal_di_bulan_terkunci(self):
		digeser = list(JANUARI_2026)
		digeser[0] = (1, date(2026, 1, 1), date(2026, 1, 3))
		digeser[1] = (2, date(2026, 1, 4), date(2026, 1, 8))

		errors = check_masa_terkunci(self.lama, masa(1, digeser), {1})
		self.assertTrue(any("tidak boleh digeser" in e for e in errors))

	def test_tolak_hapus_masa_di_bulan_terkunci(self):
		errors = check_masa_terkunci(self.lama, masa(1, JANUARI_2026[:-1]), {1})
		self.assertTrue(any("tidak boleh dihapus" in e for e in errors))

	def test_tolak_tambah_masa_di_bulan_terkunci(self):
		ditambah = list(JANUARI_2026) + [(7, date(2026, 1, 31), date(2026, 1, 31))]
		errors = check_masa_terkunci(self.lama, masa(1, ditambah), {1})
		self.assertTrue(any("tidak boleh menambah" in e for e in errors))

	def test_tidak_berubah_apa_apa_lolos(self):
		self.assertEqual(check_masa_terkunci(self.lama, list(self.lama), {1, 2}), [])

	def test_menerima_tanggal_berbentuk_string(self):
		baru = [dict(row, tanggal_mulai=str(row["tanggal_mulai"])) for row in self.lama]
		self.assertEqual(check_masa_terkunci(self.lama, baru, {1, 2}), [])
