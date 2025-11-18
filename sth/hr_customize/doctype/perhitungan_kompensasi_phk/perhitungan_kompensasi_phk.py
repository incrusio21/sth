# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe

from sth.controllers.accounts_controller import AccountsController
from frappe.utils import month_diff

class PerhitunganKompensasiPHK(AccountsController):
	def on_submit(self):
		self.make_gl_entry()

	def on_cancel(self):
		super().on_cancel()
		self.make_gl_entry()

	@frappe.whitelist()
	def fetch_perhitungan(self):
		date_of_joining = frappe.db.get_value("Employee", self.employee, "date_of_joining")
		base = frappe.db.get_value("Salary Structure Assignment", self.ssa, "base")
		setup_dasar_phk_components = frappe.db.get_all("Detail Dasar PHK", {"parent": self.dphk}, "*")
		list_perhitungan = []

		working_month = month_diff(self.l_date, date_of_joining)
		for row in setup_dasar_phk_components:
			perhitungan_component = {
				"nm": row.nm,
				"fp": row.fp,
				"gaji_pokok": base
			}
			cond = {
				"parent": row.nm,
				"from_month": ['<', working_month],
				"to_month": ['>', working_month],
			}
			setup_komponen_phk = frappe.db.get_value("Setup Komponen PHK", row.nm, "*")
			pengkali_komponen = frappe.db.get_value("Detail Setup Komponen PHK", cond, "pengkali")

			perhitungan_component.update({"fps": (pengkali_komponen if pengkali_komponen else 0)})
			result = row.fp * perhitungan_component["fps"] * base
			# if setup_komponen_phk.is_cuti:
			perhitungan_component.update({"sbttl": result})
			self.append("table_seym", perhitungan_component)

		# return list_perhitungan