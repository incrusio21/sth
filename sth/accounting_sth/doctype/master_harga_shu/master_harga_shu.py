# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (
	add_days,
	cint,
	cstr,
	date_diff,
	flt,
	get_last_day,
	getdate,
	now_datetime,
)

from sth.plantation.doctype.blok.blok import BULAN_MAP

STATUS_DRAFT = "Draft"
STATUS_DITETAPKAN = "Ditetapkan"

# Satu-satunya sumber nama bulan adalah BULAN_MAP di blok.py — jangan bikin
# salinan kedua. Peta ini cuma pembalikannya.
NAMA_BULAN = {nomor: nama for nama, nomor in BULAN_MAP.items()}

# Kolom matriks harga. Daftarnya paten, tidak ikut tahun tanam yang kebetulan
# ada di tiket timbangan: beberapa umur sengaja dihargai sama, jadi umur 15 dan
# 16 sama-sama masuk kolom "10 - 20".
#
# Kelompok terakhir menampung yang lebih tua dari 25 — kebun tua tetap terbayar.
# Di bawah 3 tahun sengaja tidak punya kolom: belum berproduksi, dan kalau toh
# ada nettonya, harganya 0 dan langsung kelihatan sebagai baris tanpa harga.
UMUR_TAK_TERHINGGA = 999

KELOMPOK_UMUR = [
	{"label": "3", "umur_min": 3, "umur_max": 3},
	{"label": "4", "umur_min": 4, "umur_max": 4},
	{"label": "5", "umur_min": 5, "umur_max": 5},
	{"label": "6", "umur_min": 6, "umur_max": 6},
	{"label": "7", "umur_min": 7, "umur_max": 7},
	{"label": "8", "umur_min": 8, "umur_max": 8},
	{"label": "9", "umur_min": 9, "umur_max": 9},
	{"label": "10 - 20", "umur_min": 10, "umur_max": 20},
	{"label": "21 - 24", "umur_min": 21, "umur_max": 24},
	{"label": "25", "umur_min": 25, "umur_max": UMUR_TAK_TERHINGGA},
]

PETA_KELOMPOK = {k["label"]: k for k in KELOMPOK_UMUR}


def kelompok_untuk_umur(umur):
	"""Kelompok umur yang memuat `umur`, atau None kalau di luar daftar.

	Fungsi murni — tanpa database.
	"""
	umur = cint(umur)

	for kelompok in KELOMPOK_UMUR:
		if kelompok["umur_min"] <= umur <= kelompok["umur_max"]:
			return kelompok

	return None


def nama_bulan(bulan_no):
	"""Label bulan: 1 jadi "Januari"."""
	return NAMA_BULAN.get(cint(bulan_no), bulan_no)


def rentang_bulan(tahun, bulan):
	"""Balikan (tanggal 1, tanggal akhir). `bulan` boleh nama Indonesia atau nomor."""
	bulan_no = cint(bulan) if cint(bulan) else BULAN_MAP.get(bulan)
	if not bulan_no or not 1 <= bulan_no <= 12:
		frappe.throw(_("Bulan tidak dikenali: {0}").format(bulan))

	awal = getdate(f"{cint(tahun):04d}-{bulan_no:02d}-01")
	return awal, getdate(get_last_day(awal))


def normalisasi_tahun_tanam(nilai):
	"""Tahun tanam ditulis sebagai Data, jadi "2010" dan "2010 " bisa hidup berdampingan.

	Tanpa normalisasi keduanya jadi dua kelompok berbeda saat dijumlahkan, dan
	yang tidak cocok dengan Master Harga SHU mengembalikan harga 0 tanpa suara.
	"""
	return cint(cstr(nilai).strip())


# ---------------------------------------------------------------------------
# Pembagian masa — fungsi murni, tanpa database
# ---------------------------------------------------------------------------


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


def check_masa_setahun(rows, tahun):
	"""Periksa pembagian masa seluruh tahun. Fungsi murni — tanpa database.

	rows: baris child table Masa, urut sesuai urutannya di form.

	Bulan yang tidak punya baris sama sekali dilewati — belum diisi itu sah,
	yang tidak sah adalah bulan yang terisi setengah. Aturan per bulannya sendiri
	tetap check_masa_rows.
	"""
	per_bulan = {}
	errors = []

	for row in rows:
		bulan_no = cint(row.get("bulan_no"))

		if not 1 <= bulan_no <= 12:
			errors.append(_("Ada baris masa yang bulannya belum diisi."))
			continue

		per_bulan.setdefault(bulan_no, []).append(row)

	if errors:
		return errors

	for bulan_no in sorted(per_bulan):
		awal = getdate(f"{cint(tahun):04d}-{bulan_no:02d}-01")
		akhir = getdate(get_last_day(awal))

		errors.extend(
			"{0}: {1}".format(nama_bulan(bulan_no), pesan)
			for pesan in check_masa_rows(per_bulan[bulan_no], awal, akhir)
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


# ---------------------------------------------------------------------------
# Harga — fungsi murni, tanpa database
# ---------------------------------------------------------------------------


def check_harga_rows(rows):
	"""Aturan 3 dan 4. Fungsi murni — tanpa database."""
	errors = []
	sudah = set()

	for row in rows:
		bulan_no = cint(row.get("bulan_no"))
		masa_no = cint(row.get("masa_no"))
		kelompok = cstr(row.get("kelompok_umur"))

		if kelompok not in PETA_KELOMPOK:
			errors.append(
				_("Bulan {0} Masa {1}: kelompok umur {2} tidak dikenali.").format(
					nama_bulan(bulan_no), masa_no, kelompok or "-"
				)
			)

		if flt(row.get("harga")) < 0:
			errors.append(
				_("Bulan {0} Masa {1} umur {2}: harga tidak boleh negatif.").format(
					nama_bulan(bulan_no), masa_no, kelompok
				)
			)

		kunci = (bulan_no, masa_no, kelompok)
		if kunci in sudah:
			errors.append(
				_("Bulan {0} Masa {1} umur {2}: barisnya ganda.").format(
					nama_bulan(bulan_no), masa_no, kelompok
				)
			)
		sudah.add(kunci)

	return errors


def check_baris_terkunci(rows_lama, rows_baru, bulan_terkunci):
	"""Aturan 6. Fungsi murni — tanpa database.

	Baris di bulan yang sudah Ditetapkan tidak boleh dihapus, diubah harganya,
	maupun ditambah. Kalau ada yang perlu diperbaiki, bulannya dibuka dulu —
	dan pembukaan itu tercatat di child table penetapan.
	"""
	if not bulan_terkunci:
		return []

	def peta(rows):
		return {
			(cint(r.get("bulan_no")), cint(r.get("masa_no")), cstr(r.get("kelompok_umur"))): flt(
				r.get("harga")
			)
			for r in rows
			if cint(r.get("bulan_no")) in bulan_terkunci
		}

	lama, baru = peta(rows_lama), peta(rows_baru)
	errors = []

	for kunci, harga_lama in lama.items():
		bulan_no, masa_no, kelompok = kunci
		label_bulan = nama_bulan(bulan_no)

		if kunci not in baru:
			errors.append(
				_("{0} sudah ditetapkan: harga Masa {1} umur {2} tidak boleh dihapus.").format(
					label_bulan, masa_no, kelompok
				)
			)
		elif baru[kunci] != harga_lama:
			errors.append(
				_("{0} sudah ditetapkan: harga Masa {1} umur {2} tidak boleh diubah ({3} menjadi {4}).").format(
					label_bulan, masa_no, kelompok, harga_lama, baru[kunci]
				)
			)

	for kunci in baru:
		if kunci not in lama:
			bulan_no, masa_no, kelompok = kunci
			errors.append(
				_("{0} sudah ditetapkan: tidak boleh menambah harga Masa {1} umur {2}.").format(
					nama_bulan(bulan_no), masa_no, kelompok
				)
			)

	return errors


def check_masa_terkunci(rows_lama, rows_baru, bulan_terkunci):
	"""Aturan 6, sisi masa. Fungsi murni — tanpa database.

	Dulu rentang tanggal terkunci karena Masa SHU disubmit. Setelah masa pindah
	ke sini penjaganya jadi penetapan per bulan: menggeser tanggal masa di bulan
	yang sudah ditetapkan sama saja dengan memindahkan harga yang sudah disepakati
	ke tanggal lain.
	"""
	if not bulan_terkunci:
		return []

	def peta(rows):
		return {
			(cint(r.get("bulan_no")), cint(r.get("masa_no"))): (
				getdate(r.get("tanggal_mulai")) if r.get("tanggal_mulai") else None,
				getdate(r.get("tanggal_selesai")) if r.get("tanggal_selesai") else None,
			)
			for r in rows
			if cint(r.get("bulan_no")) in bulan_terkunci
		}

	lama, baru = peta(rows_lama), peta(rows_baru)
	errors = []

	for kunci, tanggal_lama in lama.items():
		bulan_no, masa_no = kunci

		if kunci not in baru:
			errors.append(
				_("{0} sudah ditetapkan: Masa {1} tidak boleh dihapus.").format(
					nama_bulan(bulan_no), masa_no
				)
			)
		elif baru[kunci] != tanggal_lama:
			errors.append(
				_("{0} sudah ditetapkan: tanggal Masa {1} tidak boleh digeser ({2} s/d {3}).").format(
					nama_bulan(bulan_no), masa_no, tanggal_lama[0], tanggal_lama[1]
				)
			)

	for kunci in baru:
		if kunci not in lama:
			bulan_no, masa_no = kunci
			errors.append(
				_("{0} sudah ditetapkan: tidak boleh menambah Masa {1}.").format(
					nama_bulan(bulan_no), masa_no
				)
			)

	return errors


# ---------------------------------------------------------------------------
# Pembacaan database
# ---------------------------------------------------------------------------


def masa_setahun(company, tahun):
	"""Semua masa untuk (company, tahun).

	Satu-satunya sumber rentang tanggal SHU. Perhitungan KUD tidak pernah
	menghitung tanggal masa sendiri.
	"""
	return frappe.db.sql(
		"""
		SELECT m.name AS master_harga_shu, d.bulan_no, d.bulan,
		       d.masa_no, d.tanggal_mulai, d.tanggal_selesai, d.jumlah_hari
		FROM `tabMaster Harga SHU Masa` d
		INNER JOIN `tabMaster Harga SHU` m ON d.parent = m.name
		WHERE m.company = %(company)s
		  AND m.tahun = %(tahun)s
		ORDER BY d.bulan_no, d.masa_no
		""",
		{"company": company, "tahun": cint(tahun)},
		as_dict=True,
	)


def get_masa(company, tanggal):
	"""Masa yang memuat `tanggal` untuk company tersebut, atau None."""
	rows = frappe.db.sql(
		"""
		SELECT m.name AS master_harga_shu, m.tahun, d.bulan, d.bulan_no,
		       d.masa_no, d.tanggal_mulai, d.tanggal_selesai
		FROM `tabMaster Harga SHU Masa` d
		INNER JOIN `tabMaster Harga SHU` m ON d.parent = m.name
		WHERE m.company = %(company)s
		  AND %(tanggal)s BETWEEN d.tanggal_mulai AND d.tanggal_selesai
		LIMIT 1
		""",
		{"company": company, "tanggal": getdate(tanggal)},
		as_dict=True,
	)

	return rows[0] if rows else None


class MasterHargaSHU(Document):
	def autoname(self):
		abbr = frappe.get_cached_value("Company", self.company, "abbr")
		self.name = f"MHS-{abbr}-{cint(self.tahun):04d}"

	def validate(self):
		self.set_periode_masa()
		self.validate_masa()
		self.set_label_bulan()
		self.set_kelompok_umur()
		self.validate_harga()
		self.sinkron_masa_ke_harga()
		self.validate_baris_terkunci()
		self.set_ringkasan()

	def set_periode_masa(self):
		"""Nomor masa dan jumlah hari dihitung, tidak diketik.

		Nomor masa cuma label urutan dalam satu bulan, jadi diambil dari urutan
		barisnya di form — geser barisnya, nomornya ikut.
		"""
		urutan = {}

		for row in self.masa:
			row.bulan_no = BULAN_MAP.get(row.bulan)

			if row.bulan_no:
				urutan[row.bulan_no] = urutan.get(row.bulan_no, 0) + 1
				row.masa_no = urutan[row.bulan_no]

			if row.tanggal_mulai and row.tanggal_selesai:
				row.jumlah_hari = date_diff(row.tanggal_selesai, row.tanggal_mulai) + 1
			else:
				row.jumlah_hari = 0

		self.jumlah_masa = _("{0} bulan terisi, {1} masa").format(len(urutan), len(self.masa))

	def validate_masa(self):
		errors = check_masa_setahun([row.as_dict() for row in self.masa], self.tahun)
		if errors:
			frappe.throw("<br>".join(errors), title=_("Pembagian Masa Belum Benar"))

	def set_label_bulan(self):
		"""Baris penetapan dibuat sekali lalu dipakai terus, jadi labelnya ditulis
		ulang tiap simpan supaya ikut aturan penulisan yang berlaku sekarang."""
		for row in self.penetapan:
			row.bulan = nama_bulan(row.bulan_no)

	def set_kelompok_umur(self):
		"""Rentang umur disalin dari daftar paten ke tiap baris harga.

		Disimpan di barisnya supaya get_harga_shu() cukup mencocokkan umur dengan
		rentang lewat SQL, tanpa memetakan kelompok di Python dulu.
		"""
		for row in self.harga:
			kelompok = PETA_KELOMPOK.get(cstr(row.kelompok_umur))
			if not kelompok:
				continue

			row.umur_min = kelompok["umur_min"]
			row.umur_max = kelompok["umur_max"]

	def validate_harga(self):
		errors = check_harga_rows([row.as_dict() for row in self.harga])
		if errors:
			frappe.throw("<br>".join(errors), title=_("Data Harga Belum Benar"))

	def sinkron_masa_ke_harga(self):
		"""Aturan 5, sekaligus menyegarkan salinan tanggal.

		Tanggal disalin ke baris harga supaya get_harga_shu() cukup satu query
		tanpa join ke tabel masa. Disalin ulang tiap simpan supaya salinan itu
		tidak pernah basi.
		"""
		if not self.harga:
			return

		peta = {(cint(m.bulan_no), cint(m.masa_no)): m for m in self.masa}
		hilang = []

		for row in self.harga:
			kunci = (cint(row.bulan_no), cint(row.masa_no))
			masa = peta.get(kunci)

			if not masa:
				hilang.append(kunci)
				continue

			row.tanggal_mulai = masa.tanggal_mulai
			row.tanggal_selesai = masa.tanggal_selesai

		if hilang:
			daftar = ", ".join(
				_("{0} Masa {1}").format(nama_bulan(b), m) for b, m in sorted(set(hilang))
			)
			frappe.throw(
				_("Masa berikut sudah tidak ada di tabel Masa, padahal harganya sudah diisi: {0}").format(
					daftar
				),
				title=_("Masa Tidak Cocok"),
			)

	def validate_baris_terkunci(self):
		if self.is_new():
			return

		lama = self.get_doc_before_save()
		if not lama:
			return

		bulan_terkunci = {
			cint(row.bulan_no) for row in lama.penetapan if row.status == STATUS_DITETAPKAN
		}

		errors = check_masa_terkunci(
			[row.as_dict() for row in lama.masa],
			[row.as_dict() for row in self.masa],
			bulan_terkunci,
		)
		errors.extend(
			check_baris_terkunci(
				[row.as_dict() for row in lama.harga],
				[row.as_dict() for row in self.harga],
				bulan_terkunci,
			)
		)

		if errors:
			frappe.throw("<br>".join(errors), title=_("Bulan Sudah Ditetapkan"))

	def set_ringkasan(self):
		bulan_ditetapkan = sum(1 for row in self.penetapan if row.status == STATUS_DITETAPKAN)
		self.jumlah_sel_terisi = _("{0} sel, {1} bulan ditetapkan").format(
			len(self.harga), bulan_ditetapkan
		)

	def baris_penetapan(self, bulan_no, buat_kalau_belum_ada=False):
		for row in self.penetapan:
			if cint(row.bulan_no) == cint(bulan_no):
				return row

		if not buat_kalau_belum_ada:
			return None

		return self.append(
			"penetapan",
			{
				"bulan_no": cint(bulan_no),
				"bulan": nama_bulan(bulan_no),
				"status": STATUS_DRAFT,
			},
		)


@frappe.whitelist()
def usulan_bagi_rata(tahun, bulan, jumlah):
	"""Usulan pembagian masa sama rata untuk satu bulan. Hasilnya boleh digeser."""
	awal, akhir = rentang_bulan(tahun, bulan)
	return bagi_rata_masa(awal, akhir, jumlah)


@frappe.whitelist()
def get_masa_setahun(company, tahun):
	"""Masa satu tahun untuk pemakai di luar form ini."""
	return masa_setahun(company, tahun)


@frappe.whitelist()
def get_kelompok_umur():
	"""Kolom matriks. Dipanggil kontrol matriks supaya daftarnya cuma ada di satu tempat."""
	return KELOMPOK_UMUR


@frappe.whitelist()
def tetapkan_bulan(nama, bulan_no):
	"""Kunci satu bulan. Sel kosong dibiarkan — penetapan sebagian itu normal."""
	doc = frappe.get_doc("Master Harga SHU", nama)
	baris = doc.baris_penetapan(bulan_no, buat_kalau_belum_ada=True)

	if baris.status == STATUS_DITETAPKAN:
		frappe.throw(_("{0} sudah ditetapkan.").format(nama_bulan(bulan_no)))

	baris.status = STATUS_DITETAPKAN
	baris.ditetapkan_oleh = frappe.session.user
	baris.ditetapkan_pada = now_datetime()
	baris.catatan = None

	doc.save()
	return {"bulan": nama_bulan(bulan_no)}


@frappe.whitelist()
def buka_bulan(nama, bulan_no, alasan=None):
	"""Buka kembali bulan yang sudah ditetapkan. Pembukaannya tercatat."""
	doc = frappe.get_doc("Master Harga SHU", nama)
	baris = doc.baris_penetapan(bulan_no)

	if not baris or baris.status != STATUS_DITETAPKAN:
		frappe.throw(_("{0} belum ditetapkan.").format(nama_bulan(bulan_no)))

	baris.status = STATUS_DRAFT
	baris.catatan = _("Dibuka kembali oleh {0} pada {1}. Alasan: {2}").format(
		frappe.session.user, now_datetime(), alasan or _("tidak diisi")
	)

	doc.save()
	return {"bulan": nama_bulan(bulan_no)}


@frappe.whitelist()
def get_harga_shu(company, tanggal, tahun_tanam):
	"""Harga SHU per kg untuk satu tanggal dan tahun tanam.

	Tahun tanam dicocokkan lewat umurnya (tahun dokumen dikurangi tahun tanam),
	bukan lewat tahun tanamnya langsung — beberapa umur sengaja dihargai sama.

	Kembalikan 0 kalau belum ditetapkan atau umurnya di luar daftar kelompok —
	sengaja tidak melempar error, supaya transaksi boleh mendahului penetapan
	harga. Lubang harga dipantau lewat laporan Tanggal Tanpa Harga SHU, bukan
	lewat exception di sini.
	"""
	# Blok.tahun_tanam bertipe Data, jadi pemanggil bisa mengirim "2010 ".
	# Dinormalkan di sini supaya tidak diam-diam meleset jadi 0.
	tahun_tanam = normalisasi_tahun_tanam(tahun_tanam)
	if not tahun_tanam:
		return 0

	rows = frappe.db.sql(
		"""
		SELECT d.harga
		FROM `tabMaster Harga SHU Detail` d
		INNER JOIN `tabMaster Harga SHU` m ON d.parent = m.name
		INNER JOIN `tabMaster Harga SHU Penetapan` p
		        ON p.parent = m.name AND p.bulan_no = d.bulan_no
		WHERE m.company = %(company)s
		  AND (m.tahun - %(tahun_tanam)s) BETWEEN d.umur_min AND d.umur_max
		  AND %(tanggal)s BETWEEN d.tanggal_mulai AND d.tanggal_selesai
		  AND p.status = %(ditetapkan)s
		LIMIT 1
		""",
		{
			"company": company,
			"tahun_tanam": tahun_tanam,
			"tanggal": getdate(tanggal),
			"ditetapkan": STATUS_DITETAPKAN,
		},
		as_dict=True,
	)

	return flt(rows[0].harga) if rows else 0
