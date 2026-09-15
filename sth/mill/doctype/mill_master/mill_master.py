# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json

from frappe.model.document import Document

from sth.utils.qr_generator import get_qr_svg


class MillMaster(Document):
	def before_save(self):
		self.create_qr_pabrik()

	def create_qr_pabrik(self):
		"""QR yang ditempel di pabrik, discan saat membuat Sounding CPO / PK."""
		data = {
			"pabrik": self.name,
			"unit": self.unit,
			"latitude": self.latitude,
			"longitude": self.longitude,
		}
		self.qr_code = get_qr_svg(json.dumps(data))
