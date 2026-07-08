# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe,json
from frappe.model.document import Document
from sth.utils.qr_generator import get_qr_svg

class StationMaster(Document):
	# def validate(self):
	# 	from sth.utils.qr_generator import generate_qr_for_doc
	# 	generate_qr_for_doc(self,1)
    
	def before_save(self):
		self.create_qr_unit()

	def create_qr_unit(self):
		for row in self.detail_station_settings:
			data = {"stasiun": self.name, "unit" : row.unit , "latitude": row.latitude , "longitude": row.longitude }
			row.qr_code = get_qr_svg(json.dumps(data))