# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BukuKerjaMandorBibitan(Document):
	def _validate_links(self):
		self.make_batch()
		super()._validate_links()

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

	frappe.db.savepoint("test_bkm_bibitan")
	try:
		doc = frappe.new_doc("Buku Kerja Mandor Bibitan", **data).insert()
		hasil = {
			"ok": True,
			"name": doc.name,
			"docstatus": doc.docstatus,
			"batch": doc.batch,
			"batch_dibuat_otomatis": not batch_sudah_ada and bool(doc.batch),
		}
	except Exception as e:
		frappe.db.rollback(save_point="test_bkm_bibitan")
		frappe.clear_messages()
		return {"ok": False, "error": f"{type(e).__name__}: {e}"}

	if frappe.utils.cint(dry_run):
		frappe.db.rollback(save_point="test_bkm_bibitan")
		hasil["dry_run"] = True
	return hasil
