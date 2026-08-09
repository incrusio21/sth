# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, date_diff, get_last_day, getdate

from sth.plantation.doctype.blok.blok import BULAN_MAP


def check_masa_rows(rows, bulan_mulai, bulan_selesai):
	"""Periksa pembagian masa satu bulan. Fungsi murni — tanpa database.

	rows: list of dict berisi masa_no, tanggal_mulai, tanggal_selesai (date),
	      urut sesuai urutan baris di child table.
	Balikan: list pesan kesalahan. Kosong berarti lolos.

	Jumlah masa sengaja tidak dibatasi. Yang dijaga adalah cakupannya:
	satu bulan harus tertutup penuh, tanpa celah, tanpa tumpang tindih.
	"""
	if not rows:
		return [_("Minimal harus ada 1 masa.")]

	# Normalisasi di sini supaya pemanggil bebas mengirim date, datetime, atau string.
	rows = [
		{
			"masa_no": row.get("masa_no"),
			"tanggal_mulai": getdate(row["tanggal_mulai"]) if row.get("tanggal_mulai") else None,
			"tanggal_selesai": getdate(row["tanggal_selesai"]) if row.get("tanggal_selesai") else None,
		}
		for row in rows
	]
	bulan_mulai = getdate(bulan_mulai)
	bulan_selesai = getdate(bulan_selesai)

	errors = []

	for urutan, row in enumerate(rows, start=1):
		if cint(row.get("masa_no")) != urutan:
			errors.append(
				_("Baris ke-{0}: Masa harus bernomor {0}, bukan {1}.").format(urutan, row.get("masa_no"))
			)

	for row in rows:
		mulai, selesai = row.get("tanggal_mulai"), row.get("tanggal_selesai")
		label = row.get("masa_no")

		if not mulai or not selesai:
			errors.append(_("Masa {0}: Tanggal Mulai dan Tanggal Selesai wajib diisi.").format(label))
			continue

		if selesai < mulai:
			errors.append(
				_("Masa {0}: Tanggal Selesai ({1}) mendahului Tanggal Mulai ({2}).").format(
					label, selesai, mulai
				)
			)

		if mulai < bulan_mulai or selesai > bulan_selesai:
			errors.append(
				_("Masa {0}: tanggalnya di luar bulan ini ({1} s/d {2}).").format(
					label, bulan_mulai, bulan_selesai
				)
			)

	# Kalau ada baris yang masih cacat, cek kesinambungan tidak ada gunanya —
	# pesannya justru jadi membingungkan.
	if errors:
		return errors

	if rows[0]["tanggal_mulai"] != bulan_mulai:
		errors.append(
			_("Masa 1 harus mulai {0} (awal bulan), bukan {1}.").format(
				bulan_mulai, rows[0]["tanggal_mulai"]
			)
		)

	if rows[-1]["tanggal_selesai"] != bulan_selesai:
		errors.append(
			_("Masa {0} harus selesai {1} (akhir bulan), bukan {2}.").format(
				rows[-1]["masa_no"], bulan_selesai, rows[-1]["tanggal_selesai"]
			)
		)

	for sebelum, sesudah in zip(rows, rows[1:]):
		seharusnya = add_days(sebelum["tanggal_selesai"], 1)
		mulai_berikut = sesudah["tanggal_mulai"]

		if mulai_berikut > seharusnya:
			errors.append(
				_("Ada celah antara Masa {0} dan Masa {1}: {2} s/d {3} tidak tercakup masa manapun.").format(
					sebelum["masa_no"],
					sesudah["masa_no"],
					seharusnya,
					add_days(mulai_berikut, -1),
				)
			)
		elif mulai_berikut < seharusnya:
			errors.append(
				_("Masa {0} dan Masa {1} tumpang tindih pada {2} s/d {3}.").format(
					sebelum["masa_no"],
					sesudah["masa_no"],
					mulai_berikut,
					sebelum["tanggal_selesai"],
				)
			)

	return errors


def bagi_rata_masa(bulan_mulai, bulan_selesai, jumlah):
	"""Bagi satu bulan jadi `jumlah` masa sepanjang mungkin sama rata.

	Sisa hari dibagikan ke masa-masa terdepan supaya bulannya selalu tertutup
	penuh — hasilnya dijamin lolos check_masa_rows(). Ini cuma usulan awal;
	pembagian sesungguhnya ditentukan manual tiap bulan.
	"""
	total_hari = date_diff(bulan_selesai, bulan_mulai) + 1
	jumlah = cint(jumlah)

	if jumlah < 1:
		frappe.throw(_("Jumlah masa minimal 1."))

	if jumlah > total_hari:
		frappe.throw(
			_("Bulan ini cuma {0} hari, tidak bisa dibagi jadi {1} masa.").format(total_hari, jumlah)
		)

	panjang_dasar, sisa = divmod(total_hari, jumlah)

	rows = []
	mulai = bulan_mulai
	for i in range(jumlah):
		panjang = panjang_dasar + (1 if i < sisa else 0)
		selesai = add_days(mulai, panjang - 1)
		rows.append(
			{
				"masa_no": i + 1,
				"tanggal_mulai": mulai,
				"tanggal_selesai": selesai,
				"jumlah_hari": panjang,
			}
		)
		mulai = add_days(selesai, 1)

	return rows


def rentang_bulan(tahun, bulan):
	"""Balikan (tanggal 1, tanggal akhir) untuk nama bulan Indonesia."""
	bulan_no = BULAN_MAP.get(bulan)
	if not bulan_no:
		frappe.throw(_("Bulan tidak dikenali: {0}").format(bulan))

	awal = getdate(f"{cint(tahun):04d}-{bulan_no:02d}-01")
	return awal, getdate(get_last_day(awal))


class MasaSHU(Document):
	def autoname(self):
		bulan_no = BULAN_MAP.get(self.bulan)
		if not bulan_no:
			frappe.throw(_("Bulan tidak dikenali: {0}").format(self.bulan))

		abbr = frappe.get_cached_value("Company", self.company, "abbr")
		self.name = f"MS-{abbr}-{cint(self.tahun):04d}-{bulan_no:02d}"

	def validate(self):
		self.set_periode()
		self.set_jumlah_hari()
		self.validate_duplikat()
		self.validate_masa()

	def before_cancel(self):
		self.validate_belum_dipakai()

	def set_periode(self):
		self.bulan_no = BULAN_MAP.get(self.bulan)
		awal, akhir = rentang_bulan(self.tahun, self.bulan)
		self.tanggal_mulai = awal
		self.tanggal_selesai = akhir

	def set_jumlah_hari(self):
		for row in self.detail:
			if row.tanggal_mulai and row.tanggal_selesai:
				row.jumlah_hari = date_diff(row.tanggal_selesai, row.tanggal_mulai) + 1
			else:
				row.jumlah_hari = 0

		self.jumlah_masa = len(self.detail)

	def validate_duplikat(self):
		lain = frappe.db.exists(
			"Masa SHU",
			{
				"company": self.company,
				"tahun": self.tahun,
				"bulan": self.bulan,
				"docstatus": 1,
				"name": ("!=", self.name),
			},
		)
		if lain:
			frappe.throw(
				_("Masa SHU {0} {1} untuk {2} sudah ada dan sudah disubmit: {3}").format(
					self.bulan, self.tahun, self.company, lain
				)
			)

	def validate_masa(self):
		rows = [
			{
				"masa_no": row.masa_no,
				"tanggal_mulai": row.tanggal_mulai,
				"tanggal_selesai": row.tanggal_selesai,
			}
			for row in self.detail
		]

		errors = check_masa_rows(rows, self.tanggal_mulai, self.tanggal_selesai)
		if errors:
			frappe.throw("<br>".join(errors), title=_("Pembagian Masa Belum Benar"))

	def validate_belum_dipakai(self):
		# Master Harga SHU menyalin rentang tanggal dari sini. Membatalkan kalender
		# setelah bulannya ditetapkan akan membuat salinan itu menunjuk ke masa
		# yang sudah tidak ada.
		dipakai = frappe.db.sql(
			"""
			SELECT m.name
			FROM `tabMaster Harga SHU Penetapan` p
			INNER JOIN `tabMaster Harga SHU` m ON p.parent = m.name
			WHERE m.company = %(company)s
			  AND m.tahun = %(tahun)s
			  AND p.bulan_no = %(bulan_no)s
			  AND p.status = 'Ditetapkan'
			LIMIT 1
			""",
			{
				"company": self.company,
				"tahun": cint(self.tahun),
				"bulan_no": cint(self.bulan_no),
			},
		)

		if dipakai:
			frappe.throw(
				_(
					"Tidak bisa dibatalkan: {0} sudah ditetapkan di {1}. Buka dulu bulan itu di sana."
				).format(self.bulan, dipakai[0][0])
			)


@frappe.whitelist()
def usulan_bagi_rata(tahun, bulan, jumlah):
	"""Usulan pembagian masa sama rata. Hasilnya boleh digeser sesuka hati."""
	awal, akhir = rentang_bulan(tahun, bulan)
	return bagi_rata_masa(awal, akhir, jumlah)


@frappe.whitelist()
def get_masa(company, tanggal):
	"""Masa yang memuat `tanggal` untuk company tersebut, atau None.

	Dipakai Master Harga SHU dan Perhitungan KUD supaya keduanya membaca satu
	definisi masa yang sama.
	"""
	tanggal = getdate(tanggal)

	rows = frappe.db.sql(
		"""
		SELECT p.name AS masa_shu, p.tahun, p.bulan, p.bulan_no,
		       d.masa_no, d.tanggal_mulai, d.tanggal_selesai
		FROM `tabMasa SHU Detail` d
		INNER JOIN `tabMasa SHU` p ON d.parent = p.name
		WHERE p.docstatus = 1
		  AND p.company = %(company)s
		  AND %(tanggal)s BETWEEN d.tanggal_mulai AND d.tanggal_selesai
		LIMIT 1
		""",
		{"company": company, "tanggal": tanggal},
		as_dict=True,
	)

	return rows[0] if rows else None
