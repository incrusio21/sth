# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, cstr, flt, getdate, now_datetime

STATUS_DRAFT = "Draft"
STATUS_DITETAPKAN = "Ditetapkan"

# Di Master Harga SHU bulan ditulis dengan angka romawi: Januari jadi I.
# Masa SHU tetap memakai nama bulan.
BULAN_ROMAWI = {
	1: "I",
	2: "II",
	3: "III",
	4: "IV",
	5: "V",
	6: "VI",
	7: "VII",
	8: "VIII",
	9: "IX",
	10: "X",
	11: "XI",
	12: "XII",
}


def nama_bulan(bulan_no):
	"""Label bulan yang dipakai Master Harga SHU."""
	return BULAN_ROMAWI.get(cint(bulan_no), bulan_no)


def normalisasi_tahun_tanam(nilai):
	"""Tahun tanam ditulis sebagai Data, jadi "2010" dan "2010 " bisa hidup berdampingan.

	Tanpa normalisasi keduanya jadi dua kelompok berbeda saat dijumlahkan, dan
	yang tidak cocok dengan Master Harga SHU mengembalikan harga 0 tanpa suara.
	"""
	return cint(cstr(nilai).strip())


def tahun_tanam_per_bulan(company, tahun):
	"""{bulan_no: [tahun tanam, ...]} dari tiket timbangan sepanjang tahun itu.

	Tahun tanam tidak diketik ulang di sini, yang dipakai adalah yang sudah
	tercatat di tiket timbangan. Unitnya dibaca dari baris tiket karena unit di
	kepala tiket berisi PKS penerimanya.
	"""
	rows = frappe.db.sql(
		"""
		SELECT MONTH(t.posting_date) AS bulan_no, d.tahun_tanam
		FROM `tabTimbangan SPB Detail` d
		INNER JOIN `tabTimbangan` t ON d.parent = t.name
		INNER JOIN `tabUnit` u ON d.unit = u.name
		WHERE t.docstatus = 1
		  AND t.company = %(company)s
		  AND u.plasma = 1
		  AND YEAR(t.posting_date) = %(tahun)s
		""",
		{"company": company, "tahun": cint(tahun)},
		as_dict=True,
	)

	per_bulan = {}
	for row in rows:
		tt = normalisasi_tahun_tanam(row.tahun_tanam)
		if not tt:
			continue

		per_bulan.setdefault(cint(row.bulan_no), set()).add(tt)

	return {bulan: sorted(tts, reverse=True) for bulan, tts in sorted(per_bulan.items())}


def check_tahun_tanam(rows, tahun):
	"""Aturan 1 dan 2. Fungsi murni — tanpa database."""
	errors = []
	sudah = set()

	for row in rows:
		tt = cint(row.get("tahun_tanam"))

		if not tt:
			errors.append(_("Tahun tanam wajib diisi."))
			continue

		if tt in sudah:
			errors.append(_("Tahun tanam {0} ditulis lebih dari sekali.").format(tt))
		sudah.add(tt)

		if tt > cint(tahun):
			errors.append(
				_("Tahun tanam {0} melebihi tahun dokumen ({1}).").format(tt, cint(tahun))
			)

	return errors


def check_harga_rows(rows):
	"""Aturan 3 dan 4. Fungsi murni — tanpa database."""
	errors = []
	sudah = set()

	for row in rows:
		bulan_no = cint(row.get("bulan_no"))
		masa_no = cint(row.get("masa_no"))
		tt = cint(row.get("tahun_tanam"))

		if flt(row.get("harga")) < 0:
			errors.append(
				_("Bulan {0} Masa {1} tahun tanam {2}: harga tidak boleh negatif.").format(
					nama_bulan(bulan_no), masa_no, tt
				)
			)

		kunci = (bulan_no, masa_no, tt)
		if kunci in sudah:
			errors.append(
				_("Bulan {0} Masa {1} tahun tanam {2}: barisnya ganda.").format(
					nama_bulan(bulan_no), masa_no, tt
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
			(cint(r.get("bulan_no")), cint(r.get("masa_no")), cint(r.get("tahun_tanam"))): flt(
				r.get("harga")
			)
			for r in rows
			if cint(r.get("bulan_no")) in bulan_terkunci
		}

	lama, baru = peta(rows_lama), peta(rows_baru)
	errors = []

	for kunci, harga_lama in lama.items():
		bulan_no, masa_no, tt = kunci
		label_bulan = nama_bulan(bulan_no)

		if kunci not in baru:
			errors.append(
				_("{0} sudah ditetapkan: harga Masa {1} tahun tanam {2} tidak boleh dihapus.").format(
					label_bulan, masa_no, tt
				)
			)
		elif baru[kunci] != harga_lama:
			errors.append(
				_("{0} sudah ditetapkan: harga Masa {1} tahun tanam {2} tidak boleh diubah ({3} menjadi {4}).").format(
					label_bulan, masa_no, tt, harga_lama, baru[kunci]
				)
			)

	for kunci in baru:
		if kunci not in lama:
			bulan_no, masa_no, tt = kunci
			errors.append(
				_("{0} sudah ditetapkan: tidak boleh menambah harga Masa {1} tahun tanam {2}.").format(
					nama_bulan(bulan_no), masa_no, tt
				)
			)

	return errors


def masa_setahun(company, tahun):
	"""Semua masa dari Masa SHU yang sudah disubmit untuk (company, tahun).

	Satu-satunya sumber rentang tanggal. Master Harga SHU tidak pernah
	menghitung tanggal masa sendiri.
	"""
	return frappe.db.sql(
		"""
		SELECT p.name AS masa_shu, p.bulan_no, p.bulan,
		       d.masa_no, d.tanggal_mulai, d.tanggal_selesai, d.jumlah_hari
		FROM `tabMasa SHU Detail` d
		INNER JOIN `tabMasa SHU` p ON d.parent = p.name
		WHERE p.docstatus = 1
		  AND p.company = %(company)s
		  AND p.tahun = %(tahun)s
		ORDER BY p.bulan_no, d.masa_no
		""",
		{"company": company, "tahun": cint(tahun)},
		as_dict=True,
	)


class MasterHargaSHU(Document):
	def autoname(self):
		abbr = frappe.get_cached_value("Company", self.company, "abbr")
		self.name = f"MHS-{abbr}-{cint(self.tahun):04d}"

	def validate(self):
		self.set_label_bulan()
		self.sinkron_tahun_tanam()
		self.set_umur_tahun_tanam()
		self.validate_tahun_tanam()

	def set_label_bulan(self):
		"""Baris penetapan dibuat sekali lalu dipakai terus, jadi labelnya ditulis
		ulang tiap simpan supaya ikut aturan penulisan yang berlaku sekarang."""
		for row in self.penetapan:
			row.bulan = nama_bulan(row.bulan_no)
		self.validate_harga()
		self.sinkron_dan_validasi_masa()
		self.validate_baris_terkunci()
		self.set_ringkasan()

	def sinkron_tahun_tanam(self):
		"""Isi tabel tahun tanam dari tiket timbangan, bukan dari ketikan tangan."""
		if not self.company or not self.tahun:
			return

		per_bulan = tahun_tanam_per_bulan(self.company, self.tahun)
		dari_timbangan = {tt for daftar in per_bulan.values() for tt in daftar}

		# tahun tanam yang sudah terlanjur punya harga tetap dipertahankan, kalau
		# tidak barisnya lenyap begitu tiketnya dibatalkan dan harganya ikut hilang
		sudah_berharga = {cint(row.tahun_tanam) for row in self.harga if cint(row.tahun_tanam)}

		semua = dari_timbangan | sudah_berharga
		kelewat_tahun = sorted(tt for tt in semua if tt > cint(self.tahun))

		self.set("tahun_tanam", [])
		for tt in sorted(semua - set(kelewat_tahun), reverse=True):
			self.append("tahun_tanam", {"tahun_tanam": tt})

		if kelewat_tahun:
			frappe.msgprint(
				_("Tahun tanam {0} di tiket timbangan melebihi tahun dokumen ({1}) dan tidak ikut dipakai. Perbaiki tahun tanamnya di tiket.").format(
					", ".join(str(tt) for tt in kelewat_tahun), cint(self.tahun)
				),
				title=_("Tahun Tanam Tidak Wajar"),
				indicator="orange",
			)

	def set_umur_tahun_tanam(self):
		for row in self.tahun_tanam:
			row.umur = cint(self.tahun) - cint(row.tahun_tanam)
			row.label = f"{row.umur}TH"

	def validate_tahun_tanam(self):
		errors = check_tahun_tanam([row.as_dict() for row in self.tahun_tanam], self.tahun)
		if errors:
			frappe.throw("<br>".join(errors), title=_("Tahun Tanam Belum Benar"))

	def validate_harga(self):
		errors = check_harga_rows([row.as_dict() for row in self.harga])
		if errors:
			frappe.throw("<br>".join(errors), title=_("Data Harga Belum Benar"))

	def sinkron_dan_validasi_masa(self):
		"""Aturan 5, sekaligus menyegarkan salinan tanggal.

		Tanggal disalin ulang tiap simpan supaya salinan tidak pernah basi
		terhadap Masa SHU.
		"""
		if not self.harga:
			return

		peta = {(cint(m.bulan_no), cint(m.masa_no)): m for m in masa_setahun(self.company, self.tahun)}
		hilang = []

		for row in self.harga:
			kunci = (cint(row.bulan_no), cint(row.masa_no))
			masa = peta.get(kunci)

			if not masa:
				hilang.append(kunci)
				continue

			row.masa_shu = masa.masa_shu
			row.tanggal_mulai = masa.tanggal_mulai
			row.tanggal_selesai = masa.tanggal_selesai

		if hilang:
			daftar = ", ".join(
				_("{0} Masa {1}").format(nama_bulan(b), m) for b, m in sorted(set(hilang))
			)
			frappe.throw(
				_("Masa berikut tidak ada di Masa SHU yang sudah disubmit: {0}").format(daftar),
				title=_("Masa SHU Belum Ada"),
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

		errors = check_baris_terkunci(
			[row.as_dict() for row in lama.harga],
			[row.as_dict() for row in self.harga],
			bulan_terkunci,
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
def get_masa_setahun(company, tahun):
	"""Baris matriks. Dipanggil kontrol matriks di sisi klien."""
	return masa_setahun(company, tahun)


@frappe.whitelist()
def get_tahun_tanam_per_bulan(company, tahun):
	"""Kolom matriks per bulan. Dipanggil kontrol matriks di sisi klien."""
	return tahun_tanam_per_bulan(company, tahun)


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

	Kembalikan 0 kalau belum ditetapkan — sengaja tidak melempar error, supaya
	transaksi boleh mendahului penetapan harga. Lubang harga dipantau lewat
	laporan Tanggal Tanpa Harga SHU, bukan lewat exception di sini.
	"""
	rows = frappe.db.sql(
		"""
		SELECT d.harga
		FROM `tabMaster Harga SHU Detail` d
		INNER JOIN `tabMaster Harga SHU` m ON d.parent = m.name
		INNER JOIN `tabMaster Harga SHU Penetapan` p
		        ON p.parent = m.name AND p.bulan_no = d.bulan_no
		WHERE m.company = %(company)s
		  AND d.tahun_tanam = %(tahun_tanam)s
		  AND %(tanggal)s BETWEEN d.tanggal_mulai AND d.tanggal_selesai
		  AND p.status = %(ditetapkan)s
		LIMIT 1
		""",
		{
			"company": company,
			# Blok.tahun_tanam bertipe Data, jadi pemanggil bisa mengirim "2010 ".
			# Dinormalkan di sini supaya tidak diam-diam meleset jadi 0.
			"tahun_tanam": cint(tahun_tanam),
			"tanggal": getdate(tanggal),
			"ditetapkan": STATUS_DITETAPKAN,
		},
		as_dict=True,
	)

	return flt(rows[0].harga) if rows else 0
