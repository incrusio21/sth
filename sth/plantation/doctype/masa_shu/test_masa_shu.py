# Copyright (c) 2026, DAS and contributors
# See license.txt

from datetime import date

from frappe.tests.utils import FrappeTestCase

from sth.plantation.doctype.masa_shu.masa_shu import (
	bagi_rata_masa,
	check_masa_rows,
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
