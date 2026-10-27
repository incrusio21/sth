# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint, cstr

from sth.custom.api import submit_after_insert
from sth.mill.doctype.security_check_point.security_check_point import dari_rest_api

# Field header yang namanya sama di BKM Perawatan dan disalin apa adanya.
FIELD_HEADER_PERAWATAN = (
	"company", "posting_date", "unit", "divisi", "kemandoran",
	"kegiatan", "batch", "mandor", "kode_mandor", "trans_no",
)

# Isi baris material yang dibawa ke BKM Perawatan. rate, amount dan
# stock_entry_detail diisi Stock Entry milik BKM Perawatan saat submit.
FIELD_MATERIAL_PERAWATAN = ("item", "nama_barang", "qty", "rencana_jumlah", "warehouse")


class BukuKerjaMandorBibitan(Document):
	def insert(self, *args, **kwargs):
		"""Kiriman API dengan trans_no yang sudah tercatat digabung ke dokumen lama.

		Satu BKM Bibitan memuat semua karyawan satu trans_no, tapi perangkat
		mengirim satu request per karyawan dengan trans_no yang sama. Karyawan
		kiriman yang belum ada ditambahkan ke tabel hasil kerja dokumen lama;
		kiriman ulang karena koneksi putus — karyawannya sudah ada — tidak
		mengubah apa-apa. Dua-duanya membalas dengan dokumen lama: /api/resource
		mengirim balik isi dokumen ini, jadi pengirim menerima nomor yang sama
		seperti insert yang berhasil.

		Hanya untuk kiriman REST (atau test_insert_api). Dari form, save() juga lewat
		insert() tapi savedocs mengirim balik objek form-nya sendiri, bukan nilai
		kembalian ini — dokumen baru akan tampak tersimpan padahal tidak. Di sana
		duplikat tetap ditolak validate_trans_no_kembar.
		"""
		self.pindahkan_karyawan_kiriman()

		trans_no = cstr(self.trans_no).strip()

		if trans_no and not self.amended_from and (self.flags.dari_api or dari_rest_api()):
			kembar = get_bkm_bibitan_by_trans_no(trans_no)
			if kembar:
				return gabung_ke_bkm_bibitan(kembar, self)

		return super().insert(*args, **kwargs)

	def pindahkan_karyawan_kiriman(self):
		"""Pindahkan employee dan qty di header kiriman API ke baris hasil kerja.

		Sistem luar tetap mengirim satu karyawan di luar tabel. Header doctype ini
		sudah tidak punya field itu, jadi nilainya cuma ada sebagai atribut
		kiriman dan akan hilang begitu saja kalau tidak dipindah di sini.
		"""
		employee = self.get("employee")
		if not employee:
			return

		if not any(hk.employee == employee for hk in self.hasil_kerja):
			self.append("hasil_kerja", {"employee": employee, "qty": self.get("qty")})

		self.__dict__.pop("employee", None)
		self.__dict__.pop("qty", None)

	def before_insert(self):
		self.validate_trans_no_kembar()

		# Kiriman API datang dengan docstatus=1 langsung. Sama seperti BKM
		# Perawatan, dokumennya dijadikan draft dulu lalu disubmit di after_insert
		# supaya on_submit — yang membuat BKM Perawatan — pasti jalan.
		if self.docstatus == 1:
			self.flags.submit_after_insert = True
			self.docstatus = 0

	def after_insert(self):
		if self.flags.get("submit_after_insert"):
			submit_after_insert(self)

	def validate(self):
		self.validate_karyawan_kembar()

	def validate_karyawan_kembar(self):
		sudah_ada = set()
		for hk in self.hasil_kerja:
			if hk.employee in sudah_ada:
				frappe.throw(f"Karyawan {frappe.bold(hk.employee)} tercatat lebih dari sekali di Hasil Kerja")
			sudah_ada.add(hk.employee)

	def on_submit(self):
		self.buat_bkm_perawatan()

	def on_cancel(self):
		self.batalkan_bkm_perawatan()

	def _validate_links(self):
		self.make_batch()
		super()._validate_links()

	def validate_trans_no_kembar(self):
		"""Tolak trans_no yang sudah pernah masuk, dengan nomor dokumen lamanya di pesan.

		Dokumen amend dilewati karena memang mewarisi trans_no dokumen yang dibatalkan.
		"""
		if not self.trans_no or self.amended_from:
			return

		kembar = get_bkm_bibitan_by_trans_no(cstr(self.trans_no).strip())
		if kembar:
			frappe.throw(
				f"Buku Kerja Mandor Bibitan untuk Trans No {self.trans_no} sudah ada: {kembar}",
				frappe.DuplicateEntryError,
			)

	def make_batch(self):
		"""Kode Batch dari API dibuatkan dulu kalau belum terdaftar di Batch Bibit.

		Dijalankan dari _validate_links(), bukan before_insert atau validate: di
		insert() Frappe ini _validate_links() jalan lebih dulu daripada keduanya,
		jadi selama batch belum ada di titik itu insert ditolak "Could not find
		Kode Batch".
		"""
		if not self.batch or frappe.db.exists("Batch Bibit", self.batch):
			return

		batch_doc = frappe.new_doc("Batch Bibit")
		batch_doc.batch_id = self.batch
		batch_doc.flags.ignore_permissions = True
		batch_doc.insert()

	def get_bkm_perawatan(self):
		"""BKM Perawatan salinan dokumen ini yang belum dibatalkan, atau None."""
		return frappe.db.get_value(
			"Buku Kerja Mandor Perawatan",
			{"voucher_type": self.doctype, "voucher_no": self.name, "docstatus": ["<", 2]},
			"name",
		)

	def buat_bkm_perawatan(self):
		"""Salin dokumen ini ke BKM Perawatan dan submit salinannya.

		Upah, premi, Attendance, Stock Entry material dan GL Entry semuanya
		dikerjakan BKM Perawatan; BKM Bibitan sendiri cuma catatan kiriman.
		Tiap baris hasil kerja jadi satu baris hasil kerja BKM Perawatan.

		Aman dipanggil ulang: kalau salinannya sudah ada, tidak dibuat lagi.
		"""
		if self.get_bkm_perawatan():
			return

		kategori_kegiatan = frappe.get_cached_value("Kegiatan", self.kegiatan, "kategori_kegiatan")
		if not kategori_kegiatan:
			frappe.throw(
				f"Kegiatan {frappe.bold(self.kegiatan)} belum punya Kategori Kegiatan, "
				"BKM Perawatan tidak bisa dibuat"
			)

		bkm = frappe.new_doc("Buku Kerja Mandor Perawatan")
		bkm.update({field: self.get(field) for field in FIELD_HEADER_PERAWATAN})
		bkm.kategori_kegiatan = kategori_kegiatan
		bkm.voucher_type = self.doctype
		bkm.voucher_no = self.name
		# insert() BKM Perawatan menggabungkan kiriman API yang trans_no-nya sudah
		# ada. Salinan ini bukan kiriman API Perawatan, jadi harus tetap jadi
		# dokumennya sendiri walau trans_no-nya kebetulan sama.
		bkm.flags.dari_bkm_bibitan = True

		for baris in baris_hasil_kerja_perawatan(self.hasil_kerja):
			bkm.append("hasil_kerja", baris)

		for baris in self.material:
			bkm.append("material", {field: baris.get(field) for field in FIELD_MATERIAL_PERAWATAN})

		# docstatus=1 membuat BKM Perawatan men-submit dirinya di after_insert.
		# Bukan insert() lalu submit(): di sesi user API hook approve_api sudah
		# men-submit draft-nya lebih dulu, dan submit() kedua jadi error.
		bkm.docstatus = 1
		bkm.flags.ignore_permissions = True

		# Nomornya disamakan dengan BKM Bibitan, bukan dari series BKM-PWT, supaya
		# satu kiriman bisa dicari dengan nomor yang sama di kedua doctype.
		# Bentrok cuma mungkin kalau salinan yang dibatalkan di-amend sendiri
		# (namanya jadi BKM-BBT-xxxxx-1) lalu BKM Bibitan-nya juga di-amend.
		if frappe.db.exists("Buku Kerja Mandor Perawatan", self.name):
			frappe.throw(
				f"BKM Perawatan dengan nomor {frappe.bold(self.name)} sudah ada, "
				"salinan BKM Bibitan ini tidak bisa dibuat dengan nomor yang sama"
			)

		bkm.insert(set_name=self.name)

		frappe.msgprint(
			f"BKM Perawatan {frappe.utils.get_link_to_form(bkm.doctype, bkm.name)} dibuat",
			alert=True,
			indicator="green",
		)

	def tambah_hasil_kerja_setelah_submit(self, baris_baru):
		"""Sisipkan karyawan kiriman susulan ke dokumen yang sudah disubmit.

		save() tidak bisa dipakai — hasil_kerja bukan allow_on_submit — jadi
		barisnya ditulis langsung, dan fetch nama/NIK karyawan yang biasanya jalan
		saat save diisi sendiri. Karyawan yang sama ikut ditambahkan ke BKM
		Perawatan salinannya, supaya upah, Attendance dan GL-nya ikut terhitung.
		"""
		baris_ditambah = []
		for baris in baris_baru:
			karyawan = frappe.db.get_value(
				"Employee", baris["employee"], ["employee_name", "no_ktp"], as_dict=True
			)
			if not karyawan:
				frappe.throw(
					f"Karyawan {frappe.bold(baris['employee'])} tidak ditemukan",
					frappe.LinkValidationError,
				)

			hk = self.append("hasil_kerja", {**baris, **karyawan})
			hk.docstatus = self.docstatus
			hk.db_insert()
			baris_ditambah.append(hk)

		self.db_set("modified", frappe.utils.now(), update_modified=False)

		nama = self.get_bkm_perawatan()
		if not nama:
			# salinannya belum ada — misalnya dokumen lama yang belum tersalin —
			# jadi dibuat sekarang, sekaligus dengan baris barunya
			self.buat_bkm_perawatan()
			return

		from sth.plantation.doctype.buku_kerja_mandor_perawatan.buku_kerja_mandor_perawatan import (
			gabung_ke_bkm,
		)

		gabung_ke_bkm(nama, frappe._dict(hasil_kerja=baris_hasil_kerja_perawatan(baris_ditambah)))

	def batalkan_bkm_perawatan(self):
		"""Batalkan BKM Perawatan salinan dokumen ini.

		Harus lebih dulu dari pemeriksaan link Frappe yang jalan sesudah
		on_cancel — selama salinannya masih submitted, BKM Bibitan tidak bisa
		dibatalkan. Salinan yang masih draft dibiarkan; draft tidak menahan
		pembatalan.
		"""
		nama = frappe.db.get_value(
			"Buku Kerja Mandor Perawatan",
			{"voucher_type": self.doctype, "voucher_no": self.name, "docstatus": 1},
			"name",
		)
		if not nama:
			return

		bkm = frappe.get_doc("Buku Kerja Mandor Perawatan", nama)
		bkm.flags.ignore_permissions = True
		bkm.cancel()


def baris_hasil_kerja_perawatan(hasil_kerja):
	"""Baris hasil kerja BKM Perawatan untuk baris hasil kerja BKM Bibitan.

	Rate dan hari kerja sengaja tidak diisi: BKM Perawatan menghitungnya dari
	master Kegiatan.
	"""
	return [
		frappe._dict(employee=hk.employee, qty=hk.qty, attendance_status="Present")
		for hk in hasil_kerja
	]


def gabung_ke_bkm_bibitan(nama, kiriman):
	"""Tambahkan karyawan kiriman API ke BKM Bibitan yang trans_no-nya sama.

	Tabel material kiriman sengaja tidak ikut, sama seperti gabung_ke_bkm di BKM
	Perawatan: sistem luar mengulang seluruh isi header — termasuk material — di
	tiap request, jadi menggabungkannya berarti mengeluarkan barang yang sama
	berkali-kali.
	"""
	doc = frappe.get_doc("Buku Kerja Mandor Bibitan", nama)

	sudah_ada = {hk.employee for hk in doc.hasil_kerja}
	baris_baru = []
	for hk in kiriman.hasil_kerja:
		if not hk.employee or hk.employee in sudah_ada:
			continue

		sudah_ada.add(hk.employee)
		baris_baru.append({"employee": hk.employee, "qty": hk.qty})

	if not baris_baru:
		# kiriman ulang: karyawannya sudah tercatat semua
		return doc

	if doc.docstatus == 0:
		# masih draft: BKM Perawatan belum ada, nanti dibuat on_submit dengan
		# seluruh barisnya
		for baris in baris_baru:
			doc.append("hasil_kerja", baris)

		doc.save()
		return doc

	doc.tambah_hasil_kerja_setelah_submit(baris_baru)
	return doc


def get_bkm_bibitan_by_trans_no(trans_no):
	"""Nama BKM Bibitan yang trans_no-nya sama.

	Dokumen yang sudah dibatalkan tidak ikut dihitung supaya trans_no-nya bisa
	dikirim ulang setelah pembatalan.
	"""
	return frappe.db.get_value(
		"Buku Kerja Mandor Bibitan",
		{"trans_no": trans_no, "docstatus": ["<", 2]},
		"name",
	)


@frappe.whitelist(methods=["POST"])
def test_insert_api(payload, dry_run=1):
	"""Coba insert BKM Bibitan seperti kiriman API, untuk dites di server.

	payload berisi JSON yang sama dengan body POST /api/resource. Selama dry_run
	(default), semua perubahan — termasuk Batch Bibit yang dibuat otomatis —
	di-rollback, jadi aman diulang dengan payload yang sama.
	"""
	frappe.only_for("System Manager")

	data = frappe.parse_json(payload)
	data.pop("doctype", None)
	batch_sudah_ada = bool(data.get("batch") and frappe.db.exists("Batch Bibit", data.get("batch")))
	kembar = get_bkm_bibitan_by_trans_no(cstr(data.get("trans_no")).strip()) if data.get("trans_no") else None

	frappe.db.savepoint("test_bkm_bibitan")
	try:
		doc = frappe.new_doc("Buku Kerja Mandor Bibitan", **data)
		doc.flags.dari_api = True
		doc = doc.insert()
		hasil = {
			"ok": True,
			"name": doc.name,
			"docstatus": doc.docstatus,
			"batch": doc.batch,
			"trans_no_sudah_ada": bool(kembar),
			"karyawan": [hk.employee for hk in doc.hasil_kerja],
			"batch_dibuat_otomatis": not kembar and not batch_sudah_ada and bool(doc.batch),
		}
	except Exception as e:
		frappe.db.rollback(save_point="test_bkm_bibitan")
		frappe.clear_messages()
		return {"ok": False, "error": f"{type(e).__name__}: {e}"}

	if cint(dry_run):
		frappe.db.rollback(save_point="test_bkm_bibitan")
		hasil["dry_run"] = True
	return hasil
