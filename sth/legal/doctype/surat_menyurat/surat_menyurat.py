# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt
import re
import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import getdate

class SuratMenyurat(Document):
	def autoname(self):
		if not self.jenis_surat:
			frappe.throw("Jenis Surat wajib diisi.")

		if not self.tanggal_surat:
			frappe.throw("Tanggal Surat wajib diisi.")

		if self.jenis_surat == "Internal":
			series = "INT/.{unit}./.{abbr}./.MM./.YYYY./.#####"
		elif self.jenis_surat == "External":
			series = "EXT/.{unit}./.{abbr}./.MM./.YYYY./.#####"
		else:
			frappe.throw(f"Jenis Surat '{self.jenis_surat}' tidak dikenali.")

		tanggal = getdate(self.tanggal_surat)
		series = series.replace(".MM.", f".{tanggal.strftime('%m')}.")
		series = series.replace(".YYYY.", f".{tanggal.strftime('%Y')}.")

		def replace_field_placeholder(match):
			fieldname = match.group(1)
			value = self.get(fieldname)
			if not value:
					frappe.throw(f"Field '{fieldname}' wajib diisi untuk membentuk nomor surat.")
			return str(value)

		series = re.sub(r"\{(\w+)\}", replace_field_placeholder, series)

		self.name = make_autoname(series, doc=self)

	def validate(self):
		self.update_status_document()

	def update_status_document(self):
		file_uploaded = "Belum" if not self.file_surat else "Sudah"
		self.status = f"{file_uploaded} Upload"
