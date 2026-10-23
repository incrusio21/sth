# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BukuKerjaMandorBibitan(Document):
	def before_insert(self):
		self.make_batch()

	def make_batch(self):
		"""Kode Batch dari API dibuatkan dulu kalau belum terdaftar di Batch Bibit.

		Dijalankan di before_insert, bukan validate, karena _validate_links() jalan
		lebih dulu daripada validate: selama batch belum ada di titik itu, insert
		ditolak "Could not find Kode Batch".
		"""
		if not self.batch or frappe.db.exists("Batch Bibit", self.batch):
			return

		batch_doc = frappe.new_doc("Batch Bibit")
		batch_doc.batch_id = self.batch
		batch_doc.flags.ignore_permissions = True
		batch_doc.insert()
