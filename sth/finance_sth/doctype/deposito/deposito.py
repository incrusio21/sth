# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import date_diff, add_days, add_months, add_years

class Deposito(Document):
	def validate(self):
		self.append_bunga_cair()

	def append_bunga_cair(self):
		loop_periode = self.convert_interest_period()
		total_deposito_days = date_diff(self.tanggal_jatuh_tempo_seharusnya, self.tanggal_valuta)
		total_amount_interest = self.nilai_deposito * total_deposito_days * (self.bunga/100) / self.hari_per_tahun
		daily_interest = self.nilai_deposito * (self.bunga/100) / self.hari_per_tahun
		self.bunga_per_hari = daily_interest / self.nilai_deposito * 100
		self.amount_bunga_per_hari = daily_interest
		self.table_aodn = []
		start_date = self.tanggal_valuta
		for i in range(0, loop_periode):
			if self.periode_bunga == "Daily":
				end_date = add_days(start_date, 1)
				diff = date_diff(end_date, start_date)
				amount_interest = self.nilai_deposito * diff * (self.bunga/100) / self.hari_per_tahun
				values = {
							"status_penerimaan_bunga": "Belum Cair",
							"tanggal_penerimaan_bunga_seharusnya": end_date,
							"total_bunga_per_bulan": amount_interest,
							"nilai_penerimaan_bunga_seharusnya": amount_interest,
						}
				self.append("table_aodn", values)
			if self.periode_bunga == "Monthly":
				end_date = add_months(start_date, 1)
				diff = date_diff(end_date, start_date)
				amount_interest = self.nilai_deposito * diff * (self.bunga/100) / self.hari_per_tahun
				values = {
							"status_penerimaan_bunga": "Belum Cair",
							"tanggal_penerimaan_bunga_seharusnya": end_date,
							"total_bunga_per_bulan": amount_interest,
							"nilai_penerimaan_bunga_seharusnya": amount_interest,
						}
				self.append("table_aodn", values)
    
			start_date = end_date
		# days_diff = date_diff(self.tanggal_jatuh_tempo_seharusnya, self.tanggal_valuta)
		# accepted_days = self.tanggal_valuta
		# 	elif self.periode_bunga == "Monthly":
		# 		accepted_days = add_months(accepted_days, 1)
			
		# 	values = {
		# 		"status_penerimaan_bunga": "Belum Cair",
		# 		"tanggal_penerimaan_bunga_seharusnya": accepted_days,
		# 		"total_bunga_per_bulan": amount_interest,
		# 		"nilai_penerimaan_bunga_seharusnya": amount_interest,
		# 	}
		# 	self.append("table_aodn", values)

	def convert_interest_period(self):
		interest_period = {
			"Daily": {
				"1 Bulan": 30,
				"3 Bulan": 90,
				"6 Bulan": 180,
				"1 Tahun": 360,
				"3 Tahun": 1080,
				"5 Tahun": 1800
			},
			"Monthly": {
				"1 Bulan": 1,
				"3 Bulan": 3,
				"6 Bulan": 6,
				"1 Tahun": 12,
				"3 Tahun": 36,
				"5 Tahun": 60
			},
			"Yearly": {
				"1 Tahun": 1,
				"3 Tahun": 3,
				"5 Tahun": 5
			}
		}

		return interest_period[self.periode_bunga][self.periode_penempatan_bilyet]

	def get_maturity_date(self):
		maturity_date = self.tanggal_valuta
		if self.periode_bunga == "Daily":
			days_period = self.convert_interest_period()
			maturity_date = add_days(self.tanggal_valuta, days_period)
		elif self.periode_bunga == "Monthly":
			months_period = self.convert_interest_period()
			maturity_date = add_months(self.tanggal_valuta, months_period)
		elif self.periode_bunga == "Yearly":
			months_period = self.convert_interest_period()
			maturity_date = add_years(self.tanggal_valuta, months_period)
		self.tanggal_jatuh_tempo_seharusnya = maturity_date