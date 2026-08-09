# Copyright (c) 2026, DAS and contributors
# See license.txt

from frappe.tests.utils import FrappeTestCase

from sth.accounting_sth.doctype.master_harga_shu.master_harga_shu import (
	check_baris_terkunci,
	check_harga_rows,
	check_tahun_tanam,
)


def tt(*tahun):
	return [{"tahun_tanam": t} for t in tahun]


def harga(*spec):
	"""spec: (bulan_no, masa_no, tahun_tanam, harga)"""
	return [
		{"bulan_no": b, "masa_no": m, "tahun_tanam": t, "harga": h} for b, m, t, h in spec
	]


class TestCheckTahunTanam(FrappeTestCase):
	def test_lolos(self):
		self.assertEqual(check_tahun_tanam(tt(2012, 2011, 2010), 2026), [])

	def test_tolak_duplikat(self):
		errors = check_tahun_tanam(tt(2010, 2011, 2010), 2026)
		self.assertTrue(any("lebih dari sekali" in e for e in errors))

	def test_tolak_tahun_tanam_di_masa_depan(self):
		errors = check_tahun_tanam(tt(2027), 2026)
		self.assertTrue(any("melebihi tahun dokumen" in e for e in errors))

	def test_tahun_tanam_sama_dengan_tahun_dokumen_boleh(self):
		self.assertEqual(check_tahun_tanam(tt(2026), 2026), [])

	def test_tolak_kosong(self):
		errors = check_tahun_tanam([{"tahun_tanam": None}], 2026)
		self.assertTrue(any("wajib diisi" in e for e in errors))


class TestCheckHargaRows(FrappeTestCase):
	def test_lolos(self):
		rows = harga((1, 1, 2010, 3406.67), (1, 1, 2011, 3406.67), (1, 2, 2010, 3374.96))
		self.assertEqual(check_harga_rows(rows), [])

	def test_harga_nol_boleh(self):
		# Nol adalah harga yang sah. Yang berarti "belum ditetapkan" adalah
		# tidak adanya baris sama sekali.
		self.assertEqual(check_harga_rows(harga((1, 1, 2010, 0))), [])

	def test_tolak_harga_negatif(self):
		errors = check_harga_rows(harga((1, 1, 2010, -5)))
		self.assertTrue(any("negatif" in e for e in errors))

	def test_tolak_baris_ganda(self):
		rows = harga((1, 1, 2010, 3406.67), (1, 1, 2010, 3500))
		errors = check_harga_rows(rows)
		self.assertTrue(any("ganda" in e for e in errors))

	def test_masa_sama_tahun_tanam_beda_bukan_ganda(self):
		rows = harga((1, 1, 2010, 3406.67), (1, 1, 2011, 3406.67))
		self.assertEqual(check_harga_rows(rows), [])

	def test_bulan_beda_masa_sama_bukan_ganda(self):
		rows = harga((1, 1, 2010, 3406.67), (2, 1, 2010, 3500))
		self.assertEqual(check_harga_rows(rows), [])


class TestCheckBarisTerkunci(FrappeTestCase):
	def setUp(self):
		self.lama = harga((1, 1, 2010, 3406.67), (1, 2, 2010, 3374.96), (2, 1, 2010, 3500))

	def test_tanpa_bulan_terkunci_bebas(self):
		baru = harga((1, 1, 2010, 9999))
		self.assertEqual(check_baris_terkunci(self.lama, baru, set()), [])

	def test_bulan_tidak_terkunci_bebas_diubah(self):
		# Januari terkunci, Februari tidak — ubah Februari harus boleh.
		baru = harga((1, 1, 2010, 3406.67), (1, 2, 2010, 3374.96), (2, 1, 2010, 9999))
		self.assertEqual(check_baris_terkunci(self.lama, baru, {1}), [])

	def test_tolak_ubah_harga_di_bulan_terkunci(self):
		baru = harga((1, 1, 2010, 9999), (1, 2, 2010, 3374.96), (2, 1, 2010, 3500))
		errors = check_baris_terkunci(self.lama, baru, {1})
		self.assertTrue(any("tidak boleh diubah" in e for e in errors))

	def test_tolak_hapus_baris_di_bulan_terkunci(self):
		baru = harga((1, 1, 2010, 3406.67), (2, 1, 2010, 3500))
		errors = check_baris_terkunci(self.lama, baru, {1})
		self.assertTrue(any("tidak boleh dihapus" in e for e in errors))

	def test_tolak_tambah_baris_di_bulan_terkunci(self):
		baru = self.lama + harga((1, 1, 2011, 3406.67))
		errors = check_baris_terkunci(self.lama, baru, {1})
		self.assertTrue(any("tidak boleh menambah" in e for e in errors))

	def test_tidak_berubah_apa_apa_lolos(self):
		self.assertEqual(check_baris_terkunci(self.lama, list(self.lama), {1, 2}), [])

	def test_sel_kosong_di_bulan_terkunci_tetap_boleh_kosong(self):
		# Penetapan sebagian itu normal: 2011 tidak pernah punya baris di Januari,
		# dan itu tidak boleh dianggap pelanggaran.
		errors = check_baris_terkunci(self.lama, list(self.lama), {1})
		self.assertEqual(errors, [])
