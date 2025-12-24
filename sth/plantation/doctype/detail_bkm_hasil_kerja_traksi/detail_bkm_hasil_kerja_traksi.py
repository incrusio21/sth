# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
from frappe.utils import cstr


class DetailBKMHasilKerjaTraksi(Document):
	
	def get_kegiatan_list(self):
		if not hasattr(self, "_kegiatan_list"):
			self._kegiatan_list = [s.strip() for s in cstr(self.kegiatan_list).replace(",", "\n").split("\n") if s.strip()]

		return self._kegiatan_list
