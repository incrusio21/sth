# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint, cstr

from sth.custom.api import submit_after_insert
from sth.mill.doctype.security_check_point.security_check_point import dari_rest_api

# Field header yang namanya sama di BKM Perawatan dan disalin apa adanya.
# trans_no sengaja tidak ikut: di BKM Perawatan trans_no dipakai insert() untuk
# menggabungkan kiriman API ke dokumen yang sudah ada, jadi trans_no Bibitan yang
# kebetulan sama dengan kiriman Perawatan akan tergabung ke dokumen yang salah.
# Asalnya tetap tertelusuri lewat voucher_type/voucher_no.
FIELD_HEADER_PERAWATAN = (
	"company", "posting_date", "unit", "divisi", "kemandoran",
	"kegiatan", "batch", "mandor", "kode_mandor",
)

# Isi baris material yang dibawa ke BKM Perawatan. rate, amount dan
# stock_entry_detail diisi Stock Entry milik BKM Perawatan saat submit.
FIELD_MATERIAL_PERAWATAN = ("item", "nama_barang", "qty", "rencana_jumlah", "warehouse")


class BukuKerjaMandorBibitan(Document):
	def insert(self, *args, **kwargs):
		"""Kiriman API dengan trans_no yang sudah tercatat mengembalikan dokumen lama.

		Perangkat mengirim ulang transaksi yang sama kalau koneksinya putus padahal
		dokumennya sudah masuk. Dokumen yang sudah ada dikembalikan apa adanya —
		/api/resource membalas isi dokumen ini, jadi pengirim menerima nomor lamanya
		seperti insert yang berhasil. Isi kiriman ulang tidak ditulis ke dokumen lama.

		Hanya untuk kiriman REST (atau test_insert_api). Dari form, save() juga lewat
		insert() tapi savedocs mengirim balik objek form-nya sendiri, bukan nilai
		kembalian ini — dokumen baru akan tampak tersimpan padahal tidak. Di sana
		duplikat tetap ditolak validate_trans_no_kembar.
		"""
		trans_no = cstr(self.trans_no).strip()

		if trans_no and not self.amended_from and (self.flags.dari_api or dari_rest_api()):
			kembar = get_bkm_bibitan_by_trans_no(trans_no)
			if kembar:
				return frappe.get_doc(self.doctype, kembar)

		return super().insert(*args, **kwargs)

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
		dikerjakan BKM Perawatan; BKM Bibitan sendiri cuma catatan kiriman per
		karyawan. Karyawan dan jumlah output-nya jadi satu baris hasil kerja.

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

		bkm.append("hasil_kerja", {
			"employee": self.employee,
			"qty": self.qty,
			"attendance_status": "Present",
		})

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
