# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe,json
from frappe.model.document import Document


class Sortasi(Document):
	def validate(self):
		self.validate_rules()

	def before_submit(self):
		tim_doc = frappe.get_doc("Timbangan", self.no_timbangan)
		if self.tipe == "External":
			potongan_sortasi = frappe.utils.flt(self.potongan_sortasi_external)
		else:
			potongan_sortasi = frappe.utils.flt(self.potongan_sortasi_internal)

		tim_doc.isi_komidel = self.isi_komidel
		tim_doc.potongan_sortasi = potongan_sortasi

		# dihitung ketika get tara
		# if tim_doc.isi_komidel:
		# 	tim_doc.jumlah_janjang = tim_doc.netto / tim_doc.isi_komidel
			
		tim_doc.netto_2 = tim_doc.netto - (tim_doc.netto * tim_doc.potongan_sortasi / 100)
		tim_doc.db_update()

	def validate_rules(self):
		# TBS Mentah  ≥ 5 %
		# TBS Masak ≤ 92 %
		# TBS Busuk  ≥ 3 %
		# Tangkai Panjang ≤ 1 %
		# Sampah  ≤ 5  %
		# Berondolan < 7 %

		rules = [
			(self.p_mth >= 5 if self.tipe == "Internal" else False, "Presentase TBS mentah melebihi 5%"),
			(self.p_msk <= 92 if self.tipe == "Internal" else False, "Presentase TBS masak kurang dari 92%"),
			(self.brd_b_perc >= 3 if self.tipe == "Internal" else self.brd_e_b >= 3, "Persentase TBS Busuk melebihi 3%"),
			(self.p_tp <= 1 if self.tipe == "Internal" else False, "Persentase tangkai panjang kurang dari 1%"),
			(self.p_smph <= 5 if self.tipe == "Internal" else False, "Persentase sampah kurang dari 5%"),
			(self.p_brd < 7 if self.tipe == "Internal" else self.brd_e < 7, "Persentase berondolan kurang dari 7%")
		]

		errors = []
		for kondisi, pesan_error in rules:
			if kondisi:
				errors.append(pesan_error)
		
		self.warning_list = json.dumps(errors)
