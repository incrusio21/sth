# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe,json
from frappe.model.document import Document


class AnalisaKualitasPengirimanCPOdanKERNEL(Document):
	def validate(self):
		self.validate_rules()

	def validate_rules(self):
		
		rules = [
			(self.input_kualitas_ffa > 4.8 , "Presentase Kualitas FFA lebih besar dari 4.8%"),
			(self.input_kualitas_moisture > 0.4 if self.tipe == "CPO" else False, "Presentase Kualitas Moisture lebih besar dari 0.4%"),
			(self.input_kualitas_dirt > 0.05 if self.tipe == "CPO" else False, "Presentase Kualitas Dirt lebih besar dari 0.05%"),
		]

		errors = []
		for kondisi, pesan_error in rules:
			if kondisi:
				errors.append(pesan_error)
		
		self.warning_list = json.dumps(errors)

	def before_submit(self):
		# cari timbangan dengan no ticket ini
		list_timbangan = frappe.db.sql(""" SELECT name FROM `tabTimbangan` WHERE ticket_number = "{}" and docstatus < 2 """.format(self.ticket_number))
		for row in list_timbangan:
			print(row[0])
			doc = frappe.get_doc("Timbangan", row[0])
			doc.kualitas_ffa_ = self.input_kualitas_ffa
			doc.kualitas_broken_ = self.input_kualitas_broken

			if self.tipe == "CPO":
				doc.kualitas_moisture_ = self.input_kualitas_moisture
				doc.kualitas_dirt_ = self.input_kualitas_dirt
			elif self.tipe == "KERNEL":
				doc.kualitas_kk_ = self.input_kualitas_kk_
				doc.kualitas_ka_ = self.input_kualitas_ka_

			doc.db_update()

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_filter_ticket(doctype, txt, searchfield, start, page_len, filters):
	params = {
		"txt": f"%{txt}%",
		"start": start,
		"page_len": page_len
	}
	fcond = ""
	if filters:
		if type:=filters.get("tipe"):
			if type == "KERNEL":
				fcond += " AND i.tipe_barang = 'Palm Kernel'"
			elif type == "CPO":
				fcond += " AND i.tipe_barang = 'CPO'"

	return frappe.db.sql(f"""
		SELECT scp.name
		FROM `tabSecurity Check Point` scp 
		JOIN `tabTimbangan` t ON t.ticket_number = scp.name
		JOIN `tabItem` i ON i.name = t.kode_barang
		WHERE scp.name LIKE %(txt)s AND t.docstatus = 0 AND t.type = 'Dispatch' {fcond}
		ORDER BY scp.name
		LIMIT %(start)s, %(page_len)s
	""", params)