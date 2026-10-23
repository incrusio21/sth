# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint, cstr

from sth.mill.doctype.security_check_point.security_check_point import dari_rest_api


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
