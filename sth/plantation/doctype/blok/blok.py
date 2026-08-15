# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.model.document import Document
from frappe.utils import flt, today

BULAN_MAP = {
	"Januari": 1,
	"Februari": 2,
	"Maret": 3,
	"April": 4,
	"Mei": 5,
	"Juni": 6,
	"Juli": 7,
	"Agustus": 8,
	"September": 9,
	"Oktober": 10,
	"November": 11,
	"Desember": 12,
}

class Blok(Document):
	def validate(self):
		self.set_periode_bjr()
		self.pastikan_deskripsi_unik()

	def before_save(self):
		self.set_periode_bjr()

	def pastikan_deskripsi_unik(self):
		"""Tolak Deskripsi yang sudah dipakai Blok lain.

		Cost Center Blok dinamai dari Deskripsi. Nama dokumennya sendiri sudah
		dijaga unique lewat field `blok`, tapi Deskripsi cuma field biasa — dua
		Blok yang Deskripsi-nya kebetulan sama akan berbagi satu Cost Center, dan
		seluruh GL keduanya menumpuk di sana tanpa ada yang menegur.

		Blok yang dibatalkan dilewati supaya amend tidak tertahan oleh dokumen
		asalnya sendiri.
		"""
		if not self.deskripsi:
			return

		kembar = frappe.db.get_value(
			"Blok",
			{
				"deskripsi": self.deskripsi,
				"name": ["!=", self.name],
				"docstatus": ["!=", 2],
			},
			"name",
		)

		if kembar:
			frappe.throw(
				f"Deskripsi <b>{self.deskripsi}</b> sudah dipakai Blok {kembar}. "
				"Deskripsi dipakai sebagai nama Cost Center Blok, jadi tidak boleh kembar."
			)

	def after_insert(self):
		self.make_cost_center()

	def on_update(self):
		self.make_cost_center()

	def make_cost_center(self):
		if not self.tahun_tanam or not self.unit:
			return

		unit_doc = frappe.get_doc("Unit", self.unit)
		company = unit_doc.company
		company_doc = frappe.get_doc("Company", company)
		abbr = company_doc.abbr

		# --- Cost Center Tahun Tanam (group, parent dari blok CC) ---
		tahun_cc = _ensure_tahun_tanam_cost_center(company, abbr, self.tahun_tanam)

		# Jangan timpa cost_center kalau Blok sudah TM (cost_center-nya sudah
		# diarahkan ke Cost Center per-Blok saat naik TM, lihat naikkan_ke_tm()).
		if self.get("workflow_state") != "TM" and self.cost_center != tahun_cc:
			self.db_set("cost_center", tahun_cc, update_modified=False)

		# --- Cost Center Blok (child dari Tahun Tanam CC), nama pakai Deskripsi Blok ---
		if self.deskripsi:
			_ensure_blok_cost_center(company, abbr, self.deskripsi)

	def set_periode_bjr(self):
		if self.bulan and self.tahun:
			bulan_angka = BULAN_MAP.get(self.bulan)
			if bulan_angka:
				# Format: YYYY-MM-DD HH:MM:SS (format internal ERPNext)
				self.periode_bjr = "{}-{:02d}-01 00:00:00".format(
					int(self.tahun), bulan_angka
				)


def _ensure_tahun_tanam_cost_center(company, abbr, tahun_tanam):
	"""Pastikan Cost Center Tahun Tanam (group, parent dari blok CC) ada, lalu kembalikan namanya."""
	tahun_cc_existing = frappe.db.get_value(
		"Cost Center",
		{"cost_center_name": str(tahun_tanam), "company": company},
		"name"
	)

	if tahun_cc_existing:
		return tahun_cc_existing

	cc = frappe.new_doc("Cost Center")
	cc.cost_center_name = str(tahun_tanam)
	cc.parent_cost_center = f"Tahun Tanam - {abbr}"
	cc.company = company
	cc.is_group = 0
	cc.flags.ignore_permissions = True
	cc.insert()
	frappe.db.commit()

	return cc.name


def _ensure_blok_cost_center(company, abbr, deskripsi):
	"""Pastikan Cost Center Blok (nama = Deskripsi Blok) ada, lalu kembalikan namanya."""
	blok_cc_existing = frappe.db.get_value(
		"Cost Center",
		{"cost_center_name": deskripsi, "company": company},
		"name"
	)

	if blok_cc_existing:
		return blok_cc_existing

	blok_cc = frappe.new_doc("Cost Center")
	blok_cc.cost_center_name = deskripsi
	blok_cc.parent_cost_center = f"Blok - {abbr}"
	blok_cc.company = company
	blok_cc.is_group = 0
	blok_cc.flags.ignore_permissions = True
	blok_cc.insert()
	frappe.db.commit()

	return blok_cc.name


def _parse_list(val):
	if isinstance(val, str):
		return json.loads(val)
	return val or []


def _hitung_alokasi(blok, selected_bloks):
	"""Hitung X (biaya per hektar) dan Y (total luas Blok yang dipilih),
	nilai JE = X * Y. X & Y dihitung dari SEMUA Blok TBM di tahun tanam + unit
	yang sama (satu kelompok/cohort), sedangkan Y hanya menjumlahkan luas
	dari Blok yang dipilih user."""

	if not blok.tahun_tanam or not blok.unit:
		frappe.throw("Tahun Tanam dan Unit harus diisi.")

	if not blok.cost_center:
		frappe.throw("Cost Center belum diatur pada Blok ini.")

	cohort = frappe.get_all("Blok", filters={
		"tahun_tanam": blok.tahun_tanam,
		"unit": blok.unit,
		"workflow_state": "TBM",
	}, fields=["name", "blok", "deskripsi", "luas_areal"])

	if not cohort:
		frappe.throw("Tidak ada Blok TBM yang dapat dinaikkan.")

	cohort_by_name = {c.name: c for c in cohort}

	if not selected_bloks:
		frappe.throw("Pilih minimal satu Blok yang akan dinaikkan ke TM.")

	invalid = [s for s in selected_bloks if s not in cohort_by_name]
	if invalid:
		frappe.throw(f"Blok berikut bukan Blok TBM di Tahun Tanam/Unit yang sama: {', '.join(invalid)}")

	# JE "Naik TM" yang pernah dibuat sebelumnya ditandai dengan cost_center
	# yang sama (Tahun Tanam CC). Biaya yang sudah dipindahkan lewat JE
	# tersebut harus dikurangkan dari pool (bukan cuma dikecualikan), supaya
	# batch berikutnya menghitung dari SISA biaya yang belum dialokasikan —
	# kalau tidak, sisa Blok TBM terakhir akan kembali mendapat porsi dari
	# total biaya awal (dobel), bukan dari sisa yang sebenarnya.
	naik_tm_je_names = frappe.get_all(
		"Blok Naik TM Detail",
		filters={"parenttype": "Journal Entry"},
		pluck="parent",
		distinct=True,
	) or [""]

	# "Sudah dialokasikan" dihitung dari sisi KREDIT (bukan debit), karena
	# sejak debit JE "Naik TM" dipecah per Cost Center Blok (nama = Deskripsi
	# Blok), baris debit sudah tidak lagi berada di Cost Center Tahun Tanam.
	# Baris kredit JE "Naik TM" selalu tetap di Cost Center Tahun Tanam,
	# jadi itu yang jadi acuan berapa yang sudah terpakai dari pool.
	# Pool biaya TBM hanya diambil dari akun 126x (Aset Dalam Penyelesaian /
	# TBM). Patokannya `account_number` (sama seperti filter field Account TBM
	# di blok.js), dengan fallback ke prefix nama akun untuk akun yang
	# account_number-nya kosong tapi namanya sudah diawali nomor.
	pool_row = frappe.db.sql("""
		SELECT
			COALESCE(SUM(CASE WHEN NOT (gle.voucher_type = 'Journal Entry' AND gle.voucher_no IN %(je_names)s)
				THEN gle.debit ELSE 0 END), 0) AS pool_awal,
			COALESCE(SUM(CASE WHEN gle.voucher_type = 'Journal Entry' AND gle.voucher_no IN %(je_names)s
				THEN gle.credit ELSE 0 END), 0) AS sudah_dialokasikan
		FROM `tabGL Entry` gle
		INNER JOIN `tabAccount` acc ON acc.name = gle.account
		WHERE gle.cost_center = %(cost_center)s
		  AND gle.is_cancelled = 0
		  AND (acc.account_number LIKE '126%%' OR gle.account LIKE '126%%')
	""", {"cost_center": blok.cost_center, "je_names": tuple(naik_tm_je_names)}, as_dict=True)[0]

	total_biaya = pool_row.pool_awal or 0
	sisa_biaya = total_biaya - (pool_row.sudah_dialokasikan or 0)

	total_hektar = sum(c.luas_areal or 0 for c in cohort)
	if not total_hektar:
		frappe.throw("Total Luas Areal Blok TBM di Tahun Tanam ini adalah 0.")

	x_per_hektar = sisa_biaya / total_hektar
	y_luas_dipilih = sum(cohort_by_name[s].luas_areal or 0 for s in selected_bloks)
	total = x_per_hektar * y_luas_dipilih

	return {
		"cohort": cohort,
		"selected": [cohort_by_name[s] for s in selected_bloks],
		"total_biaya": total_biaya,
		"total_hektar": total_hektar,
		"x_per_hektar": x_per_hektar,
		"y_luas_dipilih": y_luas_dipilih,
		"total": total,
	}


@frappe.whitelist()
def get_tbm_bloks_for_selection(blok_name):
	blok = frappe.get_doc("Blok", blok_name)

	if blok.get("workflow_state") != "TBM":
		frappe.throw("Blok ini tidak dalam status TBM.")

	if not blok.tahun_tanam or not blok.unit:
		frappe.throw("Tahun Tanam dan Unit harus diisi.")

	cohort = frappe.get_all("Blok", filters={
		"tahun_tanam": blok.tahun_tanam,
		"unit": blok.unit,
		"workflow_state": "TBM",
	}, fields=["name", "blok", "luas_areal"], order_by="blok asc")

	return {
		"tahun_tanam": blok.tahun_tanam,
		"unit": blok.unit,
		"bloks": cohort,
	}


@frappe.whitelist()
def preview_naikkan_ke_tm(blok_name, selected_bloks):
	blok = frappe.get_doc("Blok", blok_name)
	selected_bloks = _parse_list(selected_bloks)

	alokasi = _hitung_alokasi(blok, selected_bloks)

	unit_doc = frappe.get_doc("Unit", blok.unit)
	company = unit_doc.company

	debit_account = frappe.db.get_value("Account", {"account_number": "1271301", "company": company}, "name") or "1271301 - TANAMAN MENGHASILKAN"
	credit_account = frappe.db.get_value("Account", {"account_number": "1269999", "company": company}, "name") or "1269999 - ASET DALAM PENYELESAIAN - LAINNYA"

	return {
		"jumlah_blok": len(alokasi["selected"]),
		"jumlah_blok_cohort": len(alokasi["cohort"]),
		"total_biaya": alokasi["total_biaya"],
		"total_hektar": alokasi["total_hektar"],
		"luas_dipilih": alokasi["y_luas_dipilih"],
		"total": alokasi["total"],
		"debit_account": debit_account,
		"credit_account": credit_account,
		"tahun_tanam": blok.tahun_tanam,
		"unit": blok.unit,
	}


@frappe.whitelist()
def naikkan_ke_tm(blok_name, selected_bloks):
	blok = frappe.get_doc("Blok", blok_name)
	selected_bloks = _parse_list(selected_bloks)

	if blok.get("workflow_state") != "TBM":
		frappe.throw("Blok ini tidak dalam status TBM.")

	alokasi = _hitung_alokasi(blok, selected_bloks)
	total = alokasi["total"]
	selected = alokasi["selected"]

	unit_doc = frappe.get_doc("Unit", blok.unit)
	company = unit_doc.company
	abbr = frappe.get_doc("Company", company).abbr

	missing_deskripsi = [b.blok for b in selected if not b.deskripsi]
	if missing_deskripsi:
		frappe.throw(
			f"Deskripsi belum diisi pada Blok berikut: {', '.join(missing_deskripsi)}. "
			"Deskripsi dibutuhkan untuk penamaan Cost Center saat naik TM."
		)

	debit_account = frappe.db.get_value("Account", {
		"account_number": "1271301",
		"company": company,
	}, "name")
	credit_account = frappe.db.get_value("Account", {
		"account_number": "1269999",
		"company": company,
	}, "name")

	if not debit_account:
		frappe.throw(f"Akun 1271301 tidak ditemukan untuk company {company}.")
	if not credit_account:
		frappe.throw(f"Akun 1269999 tidak ditemukan untuk company {company}.")

	if not frappe.db.exists("Kategori Kegiatan", "TM"):
		frappe.throw('Kategori Kegiatan "TM" tidak ditemukan.')

	je_name = None
	x_per_hektar = alokasi["x_per_hektar"]

	if total:
		tahun_cc = _ensure_tahun_tanam_cost_center(company, abbr, blok.tahun_tanam)

		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Journal Entry"
		je.posting_date = today()
		je.company = company
		nama_blok_dipilih = ", ".join(b.blok for b in selected)
		je.user_remark = (
			f"Naik TM - Tahun Tanam {blok.tahun_tanam} Unit {blok.unit} - Blok: {nama_blok_dipilih}"
		)

		# Debit per Blok, cost center pakai Cost Center Blok (nama = Deskripsi Blok).
		# Dibulatkan per baris; sisa pembulatan diserap baris terakhir supaya
		# Total Debit == Total Credit persis (hindari ValidationError).
		sisa_total = flt(total, precision=2)
		for i, b in enumerate(selected):
			blok_cc = _ensure_blok_cost_center(company, abbr, b.deskripsi)
			if i == len(selected) - 1:
				debit_amount = sisa_total
			else:
				debit_amount = flt(x_per_hektar * (b.luas_areal or 0), precision=2)
				sisa_total = flt(sisa_total - debit_amount, precision=2)
			je.append("accounts", {
				"account": debit_account,
				"debit_in_account_currency": debit_amount,
				"credit_in_account_currency": 0,
				"cost_center": blok_cc,
			})

		je.append("accounts", {
			"account": credit_account,
			"debit_in_account_currency": 0,
			"credit_in_account_currency": total,
			"cost_center": tahun_cc,
		})

		for b in selected:
			je.append("naik_tm_bloks", {"blok": b.name})

		je.flags.ignore_permissions = True
		je.insert()
		je.submit()
		je_name = je.name

	for b in selected:
		blok_cc = _ensure_blok_cost_center(company, abbr, b.deskripsi)
		frappe.db.set_value("Blok", b.name, {
			"workflow_state": "TM",
			"naik_tm_journal_entry": je_name,
			"cost_center": blok_cc,
			"status": "TM",
		}, update_modified=False)

	frappe.db.commit()

	return {
		"blok_diproses": len(selected),
		"journal_entry": je_name,
		"total": total,
	}


@frappe.whitelist()
def naikkan_ke_tm_1_blok(blok_name):
	"""Naikkan satu Blok ke TM saja (alokasi biaya tetap dihitung dari
	seluruh cohort Blok TBM di Tahun Tanam + Unit yang sama, tapi hanya
	Blok ini yang diproses naik TM)."""
	return naikkan_ke_tm(blok_name, [blok_name])


@frappe.whitelist()
def kembalikan_ke_tbm(blok_name):
	blok = frappe.get_doc("Blok", blok_name)

	if blok.get("workflow_state") != "TM":
		frappe.throw("Blok ini tidak dalam status TM.")

	je_name = blok.naik_tm_journal_entry

	if je_name:
		blok_list = frappe.get_all("Blok", filters={
			"naik_tm_journal_entry": je_name,
			"workflow_state": "TM",
		}, fields=["name"])
	else:
		blok_list = [frappe._dict({"name": blok.name})]

	if not blok_list:
		frappe.throw("Tidak ada Blok TM yang terkait dengan Journal Entry ini.")

	unit_doc = frappe.get_doc("Unit", blok.unit)
	company = unit_doc.company
	abbr = frappe.get_doc("Company", company).abbr
	tahun_cc = _ensure_tahun_tanam_cost_center(company, abbr, blok.tahun_tanam)

	for b in blok_list:
		frappe.db.set_value("Blok", b.name, {
			"workflow_state": "TBM",
			"naik_tm_journal_entry": None,
			"cost_center": tahun_cc,
		}, update_modified=False)

	if je_name:
		je = frappe.get_doc("Journal Entry", je_name)
		if je.docstatus == 1:
			je.flags.ignore_permissions = True
			je.cancel()

	frappe.db.commit()

	return {
		"blok_diproses": len(blok_list),
		"journal_entry": je_name,
	}
