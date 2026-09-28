# Copyright (c) 2026, DAS and contributors
# See license.txt

"""Accrual Payroll Entry: satu baris GL per akun komponen.

Yang diuji di sini susun_gl_accrual, bukan posting-nya. Dia memulangkan baris
GL tanpa menyentuh buku besar (lihat docstring-nya), jadi seluruh berkas ini
jalan tanpa Employee, Salary Structure, atau Salary Slip sungguhan: slip dan
rincian komponennya dipasok dari sini, sebentuk dengan yang dipulangkan
get_slip_accrual dan rincian_komponen.

Perhatian utamanya PPh21. Potongan PPh21 punya akun sendiri di tabel Accounts
Salary Component, dan di sebagian company akun itu sama dengan akun beban
gajinya - kalau debit dan kreditnya sampai dijaring jadi satu baris netto,
PPh21 yang dipotong dari karyawan tidak pernah kelihatan di buku besar.
"""

from datetime import date
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from sth.overrides.payroll_entry import PayrollEntry

BEBAN_KEBUN = "4121001 - BIAYA GAJI DIALOKASI - TML"
BEBAN_MILL = "4211001 - ALOKASI BIAYA PABRIK - TML"
HUTANG_BPJS = "2161003 - HUTANG BPJS - TML"
HUTANG_GAJI = "2161001 - HUTANG GAJI DAN UPAH - TML"
HUTANG_PPH21 = "2161005 - HUTANG PPH 21 - TML"

CC_UMUM = "UMUM - TML"
CC_STASIUN = "STASIUN PRESSING - TML"


def slip(name, net_pay, total_loan_repayment=0):
	"""Satu baris hasil get_slip_accrual."""
	return frappe._dict({
		"name": name,
		"employee": "EMP-" + name,
		"employee_name": "Karyawan " + name,
		"net_pay": net_pay,
		"total_loan_repayment": total_loan_repayment,
		"stasiun": None,
		"unit": "TML",
		"mill": 0,
	})


def komponen(salary_slip, salary_component, account, amount):
	"""Satu baris hasil rincian_komponen."""
	return frappe._dict({
		"salary_slip": salary_slip,
		"employee": "EMP-" + salary_slip,
		"employee_name": "Karyawan " + salary_slip,
		"salary_component": salary_component,
		"amount": amount,
		"account": account,
	})


class PayrollEntryPalsu:
	"""Payroll Entry secukupnya untuk susun_gl_accrual, tanpa lewat database.

	Dua method yang memukul database - get_slip_accrual dan cost_center_per_slip
	- diganti pasokan dari test; sisanya method aslinya yang jalan.
	"""

	doctype = "Payroll Entry"

	susun_gl_accrual = PayrollEntry.susun_gl_accrual
	setarakan_accrual = PayrollEntry.setarakan_accrual

	def __init__(self, slips, cost_center_slip, payroll_payable_account=HUTANG_GAJI):
		self.name = "HR-PRUN-TEST-0001"
		self.company = "PT. TRIMITRA LESTARI"
		self.posting_date = date(2026, 9, 30)
		self.cost_center = CC_UMUM
		self.payroll_payable_account = payroll_payable_account
		self._slips = slips
		self._cost_center_slip = cost_center_slip

	def get_slip_accrual(self):
		return self._slips

	def cost_center_per_slip(self, slips):
		return self._cost_center_slip


class TestAccrualPayrollEntry(FrappeTestCase):
	def susun(self, slips, cost_center_slip, earnings, deductions, **kwargs):
		"""Jalankan susun_gl_accrual dengan rincian komponen yang dipasok test."""
		doc = PayrollEntryPalsu(slips, cost_center_slip, **kwargs)

		def rincian(company, nama_slip, parentfield="earnings", hanya_kegiatan_kebun=False):
			baris = earnings if parentfield == "earnings" else deductions
			return [d for d in baris if d.salary_slip in nama_slip]

		with patch("sth.overrides.payroll_entry.rincian_komponen", side_effect=rincian):
			return doc.susun_gl_accrual()

	def baris_akun(self, gl_entries, account, cost_center=None):
		return [
			d for d in gl_entries
			if d.account == account and (cost_center is None or d.cost_center == cost_center)
		]

	def test_komponen_seakun_jadi_satu_baris_akun_beda_terpisah(self):
		"""Yang dikelompokkan akunnya, bukan nama komponennya."""
		gl_entries, payable = self.susun(
			slips=[slip("SS-0001", net_pay=9_000_000)],
			cost_center_slip={"SS-0001": CC_UMUM},
			earnings=[
				komponen("SS-0001", "Gaji Pokok-Opr Kebun", BEBAN_KEBUN, 6_000_000),
				komponen("SS-0001", "Upah Panen", BEBAN_KEBUN, 2_000_000),
				komponen("SS-0001", "Gaji Pokok-Opr Mill", BEBAN_MILL, 1_000_000),
			],
			deductions=[],
		)

		self.assertEqual(payable, 9_000_000)

		kebun = self.baris_akun(gl_entries, BEBAN_KEBUN)
		self.assertEqual(len(kebun), 1)
		self.assertEqual(kebun[0].debit, 8_000_000)

		mill = self.baris_akun(gl_entries, BEBAN_MILL)
		self.assertEqual(len(mill), 1)
		self.assertEqual(mill[0].debit, 1_000_000)

		self.assertEqual(self.baris_akun(gl_entries, HUTANG_GAJI)[0].credit, 9_000_000)

	def test_pph21_dikreditkan_ke_akun_potongannya_sendiri(self):
		"""Potongan PPh21 punya baris kreditnya sendiri, bukan ikut net pay."""
		gl_entries, payable = self.susun(
			slips=[slip("SS-0001", net_pay=9_606_645)],
			cost_center_slip={"SS-0001": CC_UMUM},
			earnings=[komponen("SS-0001", "Gaji Pokok-Opr Kebun", BEBAN_KEBUN, 10_000_000)],
			deductions=[komponen("SS-0001", "PPH21 TER", HUTANG_PPH21, 393_355)],
		)

		pph21 = self.baris_akun(gl_entries, HUTANG_PPH21)
		self.assertEqual(len(pph21), 1)
		self.assertEqual(pph21[0].credit, 393_355)
		self.assertEqual(pph21[0].debit, 0)
		self.assertEqual(pph21[0].cost_center, CC_UMUM)

		self.assertEqual(payable, 9_606_645)
		self.assertEqual(self.baris_akun(gl_entries, HUTANG_GAJI)[0].credit, 9_606_645)

	def test_pph21_seakun_dengan_beban_tetap_dua_baris(self):
		"""Akun PPh21 yang sama dengan akun beban tidak dinettokan jadi satu baris.

		Ini konfigurasi yang dipakai TML: PPh21 dan beban gaji operator kebun
		sama-sama menunjuk 4121001. Kalau dijaring jadi satu baris netto,
		potongan PPh21-nya hilang dari buku besar.
		"""
		gl_entries, payable = self.susun(
			slips=[slip("SS-0001", net_pay=9_606_645)],
			cost_center_slip={"SS-0001": CC_UMUM},
			earnings=[komponen("SS-0001", "Gaji Pokok-Opr Kebun", BEBAN_KEBUN, 10_000_000)],
			deductions=[komponen("SS-0001", "PPH21 TER", BEBAN_KEBUN, 393_355)],
		)

		baris = self.baris_akun(gl_entries, BEBAN_KEBUN)
		self.assertEqual(len(baris), 2)
		self.assertEqual([d.debit for d in baris], [10_000_000, 0])
		self.assertEqual([d.credit for d in baris], [0, 393_355])
		self.assertEqual(payable, 9_606_645)

	def test_pph21_dipisah_per_cost_center(self):
		"""Potongan karyawan mill jatuh di cost center stasiunnya, bukan cost center dokumen."""
		gl_entries, payable = self.susun(
			slips=[slip("SS-0001", net_pay=4_800_000), slip("SS-0002", net_pay=4_900_000)],
			cost_center_slip={"SS-0001": CC_UMUM, "SS-0002": CC_STASIUN},
			earnings=[
				komponen("SS-0001", "Gaji Pokok-Opr Kebun", BEBAN_KEBUN, 5_000_000),
				komponen("SS-0002", "Gaji Pokok-Opr Mill", BEBAN_MILL, 5_000_000),
			],
			deductions=[
				komponen("SS-0001", "PPH21 TER", HUTANG_PPH21, 200_000),
				komponen("SS-0002", "PPH21 TER", HUTANG_PPH21, 100_000),
			],
		)

		pph21 = self.baris_akun(gl_entries, HUTANG_PPH21)
		self.assertEqual(len(pph21), 2)
		self.assertEqual(
			{(d.cost_center, d.credit) for d in pph21},
			{(CC_UMUM, 200_000), (CC_STASIUN, 100_000)},
		)
		self.assertEqual(payable, 9_700_000)

	def test_jurnalnya_seimbang(self):
		"""Total debit sama dengan total kredit, termasuk waktu ada PPh21 dan BPJS."""
		gl_entries, payable = self.susun(
			slips=[slip("SS-0001", net_pay=8_933_357.88, total_loan_repayment=500_000)],
			cost_center_slip={"SS-0001": CC_UMUM},
			earnings=[
				komponen("SS-0001", "Gaji Pokok-Opr Kebun", BEBAN_KEBUN, 9_000_000),
				komponen("SS-0001", "Upah Panen", BEBAN_KEBUN, 1_000_000),
			],
			deductions=[
				komponen("SS-0001", "PPH21 TER", HUTANG_PPH21, 393_355),
				komponen("SS-0001", "BPJS Kesehatan (Karyawan)", HUTANG_BPJS, 173_287.12),
			],
		)

		self.assertEqual(payable, 9_433_357.88)
		self.assertEqual(
			flt(sum(flt(d.debit) for d in gl_entries), 2),
			flt(sum(flt(d.credit) for d in gl_entries), 2),
		)

	def test_sisa_pembulatan_ditimpakan_ke_debit_terbesar(self):
		"""Selisih serupiah dua rupiah ditumpangkan, bukan dibiarkan pincang."""
		gl_entries, payable = self.susun(
			slips=[slip("SS-0001", net_pay=9_606_644.50)],
			cost_center_slip={"SS-0001": CC_UMUM},
			earnings=[
				komponen("SS-0001", "Gaji Pokok-Opr Kebun", BEBAN_KEBUN, 10_000_000),
				komponen("SS-0001", "Premi Panen", BEBAN_MILL, 100_000),
			],
			deductions=[komponen("SS-0001", "PPH21 TER", HUTANG_PPH21, 493_355)],
		)

		self.assertEqual(payable, 9_606_644.50)
		self.assertEqual(self.baris_akun(gl_entries, BEBAN_KEBUN)[0].debit, 9_999_999.50)
		self.assertEqual(self.baris_akun(gl_entries, BEBAN_MILL)[0].debit, 100_000)
		self.assertEqual(
			flt(sum(flt(d.debit) for d in gl_entries), 2),
			flt(sum(flt(d.credit) for d in gl_entries), 2),
		)

	def test_selisih_lebih_dari_serupiah_dilempar(self):
		"""Selisih sebesar itu bukan pembulatan - ada komponen yang penyaringnya beda."""
		with self.assertRaises(frappe.ValidationError):
			self.susun(
				slips=[slip("SS-0001", net_pay=5_000_000)],
				cost_center_slip={"SS-0001": CC_UMUM},
				earnings=[komponen("SS-0001", "Gaji Pokok-Opr Kebun", BEBAN_KEBUN, 10_000_000)],
				deductions=[komponen("SS-0001", "PPH21 TER", HUTANG_PPH21, 393_355)],
			)

	def test_tanpa_komponen_dilempar(self):
		"""Slip yang semua komponennya tersaring habis tidak boleh diam-diam lolos."""
		with self.assertRaises(frappe.ValidationError):
			self.susun(
				slips=[slip("SS-0001", net_pay=0)],
				cost_center_slip={"SS-0001": CC_UMUM},
				earnings=[],
				deductions=[],
			)
