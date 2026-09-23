# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from sth.mill.doctype.data_tbs.data_tbs import perbarui_jam_olah


class CBCMonitoring(Document):
	def on_submit(self):
		self.perbarui_data_tbs()

	def on_cancel(self):
		self.perbarui_data_tbs()

	def perbarui_data_tbs(self):
		# Jam olah Data TBS dibaca waktu Get Data, jadi CBC yang di-amend sesudah
		# Data TBS-nya disubmit tidak akan terbaca lagi tanpa ini.
		perbarui_jam_olah(self.unit, self.posting_date)
