# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from sth.mill.utils import set_total_jam_desimal


class BukuKerjaMekanik(Document):
	def validate(self):
		set_total_jam_desimal(self)
