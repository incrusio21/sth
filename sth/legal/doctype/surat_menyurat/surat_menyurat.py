# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import getdate

class SuratMenyurat(Document):
	def autoname(self):
		frappe.throw("CUSTOM AUTONAME TERPANGGIL")

		if not self.naming_series:
			frappe.throw("Naming Series wajib diisi.")

		if not self.tanggal_surat:
			frappe.throw("Tanggal Surat wajib diisi.")

		tanggal = getdate(self.tanggal_surat)
		series = self.naming_series
		series = series.replace(
			".MM.",
			f".{tanggal.strftime('%m')}."
		)

		series = series.replace(
			".YYYY.",
			f".{tanggal.strftime('%Y')}."
		)

		self.name = make_autoname(
			series,
			doc=self
		)

	def validate(self):
		self.update_status_document()

	def update_status_document(self):
		file_uploaded = "Belum" if not self.file_surat else "Sudah"
		self.status = f"{file_uploaded} Upload"
