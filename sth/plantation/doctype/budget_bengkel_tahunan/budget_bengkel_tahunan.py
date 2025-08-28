# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, get_link_to_form
from sth.controllers.budget_controller import BudgetController

class BudgetBengkelTahunan(BudgetController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.skip_table_amount = ["distribusi"]
		self.duplicate_param.extend([
			"kode_bengkel"
		])

	def validate(self):
		super().validate()
		self.set_rp_per_jam()
		self.validate_kendaraan_distribusi_rate()

	def on_submit(self):
		self.update_budget_traksi()
	
	def set_rp_per_jam(self):
		self.rp_kmhm = self.grand_total / self.jam_per_tahun
		
	def validate_kendaraan_distribusi_rate(self):
		if not self.distribusi:
			return
		
		total_jam = 0
		all_kendaraan = []
		bbt = frappe.qb.DocType("Budget Bengkel Tahunan")
		bdt = frappe.qb.DocType("Detail Budget Distribusi Traksi")

		# query untuk mengecek kendaraan tersebut telah d pakai untuk budget d tahun tersebut
		query = (
			frappe.qb.from_(bdt)
			.inner_join(bbt)
			.on(bdt.name == bbt.parent)
			.select(
				bdt.item, bbt.name
            )
			.where(
                (bdt.docstatus == 1) &
				(bbt.name != self.name) & 
				(bdt.budget_kebun_tahunan == self.budget_kebun_tahunan) &
				(bdt.divisi == self.divisi)
			)
		)

		for d in self.distribusi:
			total_jam += d.qty
			d.rate = self.rp_kmhm
			all_kendaraan.append(d.item)

		query = query.where(bdt.isin(all_kendaraan))
		if kendaraan_exist := query.run(as_dict=True):
			message = "There is a duplicate vehicle against the Budget Bengkel"
			for ex in kendaraan_exist:
				message += f"<br>{ex.item} in {get_link_to_form(self.doctype, ex.name)}"

		# hitung ulang nilai distribusi
		self.calculate_item_values("Detail Budget Distribusi", "distribusi")

		if total_jam > self.jam_per_tahun:
			frappe.throw("Total distribution exceeds annual workshop hours.")

	def update_budget_traksi(self):
		if not self.distribusi:
			return

		# get all traksi sudah ada
		all_vehicle = frappe.get_all("Budget Traksi Tahunan", filters={
			"budget_kebun_tahunan": self.budget_kebun_tahunan, "divisi": self.divisi,
			"docstatus": 1,
			"kode_kendaraan": ["in", [x.item for x in self.distribusi]]
		}, pluck="name")

		# lakukan validasi ulang untuk traksi
		for traksi in all_vehicle:
			doc = frappe.get_doc("Budget Traksi Tahunan", traksi)
			doc.validate()

			doc.db_update()
			doc.update_children()

