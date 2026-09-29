# Copyright (c) 2026, DAS and Contributors
# See license.txt

from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from sth.accounting_sth.doctype.nota_piutang.nota_piutang import (
	hitung_dpp_ppn,
	pecah_dpp_ppn,
	tambah_ppn,
)


class TestPecahDppPpn(FrappeTestCase):
	"""Pemecah nilai gross jadi DPP dan PPN. Tanpa database."""

	def test_tarif_11_persen(self):
		dpp, ppn = pecah_dpp_ppn(1_110_000, 11)

		self.assertEqual(dpp, 1_000_000)
		self.assertEqual(ppn, 110_000)

	def test_tarif_12_persen(self):
		dpp, ppn = pecah_dpp_ppn(1_120_000, 12)

		self.assertEqual(dpp, 1_000_000)
		self.assertEqual(ppn, 120_000)

	def test_tanpa_tarif_seluruhnya_dpp(self):
		"""Tarif nol dipakai sub tipe yang dicentang Tanpa PPN."""
		dpp, ppn = pecah_dpp_ppn(1_110_000, 0)

		self.assertEqual(dpp, 1_110_000)
		self.assertEqual(ppn, 0)

	def test_pecahan_selalu_berjumlah_grossnya(self):
		"""Yang tidak habis dibagi tetap tidak boleh menyisakan selisih sesen."""
		for nilai in (1_961_473.78, 1_000_000, 333_333.33, 0.01, 12_345.67):
			dpp, ppn = pecah_dpp_ppn(nilai, 11)

			self.assertEqual(flt(dpp + ppn, 2), flt(nilai, 2), msg=f"nilai {nilai}")

	def test_nilai_nol(self):
		self.assertEqual(pecah_dpp_ppn(0, 11), (0, 0))


class TestTambahPpn(FrappeTestCase):
	"""Nilai yang belum termasuk PPN: utuh jadi DPP, PPN di atasnya. Tanpa database."""

	def test_tarif_11_persen(self):
		self.assertEqual(tambah_ppn(1_000_000, 11), (1_000_000, 110_000))

	def test_dibulatkan_ke_sen(self):
		self.assertEqual(tambah_ppn(1_961_473.78, 11), (1_961_473.78, 215_762.12))

	def test_tanpa_tarif(self):
		self.assertEqual(tambah_ppn(1_000_000, 0), (1_000_000, 0))


class TestHitungDppPpn(FrappeTestCase):
	def test_exclude_menambahkan(self):
		self.assertEqual(hitung_dpp_ppn(1_000_000, 11, "Exclude"), (1_000_000, 110_000))

	def test_include_memecah(self):
		self.assertEqual(hitung_dpp_ppn(1_110_000, 11, "Include"), (1_000_000, 110_000))

	def test_kosong_dianggap_include(self):
		"""Nota yang dibuat sebelum ada Jenis PPN."""
		self.assertEqual(hitung_dpp_ppn(1_110_000, 11, None), (1_000_000, 110_000))


class TestNotaPiutang(FrappeTestCase):
	pass
