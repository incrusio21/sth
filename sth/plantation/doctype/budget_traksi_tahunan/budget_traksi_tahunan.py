# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.query_builder.custom import ConstantColumn
from frappe.utils import flt
from sth.controllers.budget_controller import BudgetController


class BudgetTraksiTahunan(BudgetController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.duplicate_param.extend([
			"divisi", "kode_kendaraan"
		])

	def validate(self):
		self.set_biaya_bengkel()
		super().validate()
		self.set_rp_per_km_hm()

	def set_biaya_bengkel(self):
		self.set("bengkel",
			get_biaya_bengkel(self.budget_kebun_tahunan, self.divisi, self.kode_kendaraan)
		)
	
	def set_rp_per_km_hm(self):
		self.rp_kmhm = flt(self.grand_total / self.total_km_hm, self.precision("rp_kmhm"))


@frappe.whitelist()
def get_biaya_bengkel(tahun_budget, divisi, kendaraan):
	bbt = frappe.qb.DocType("Budget Bengkel Tahunan")
	bdt = frappe.qb.DocType("Detail Budget Distribusi Traksi")

	list_biaya_bengkel = (
		frappe.qb.from_(bdt)
		.inner_join(bbt)
		.on(bbt.name == bdt.parent)
		.select(
			bbt.name.as_("item"), bdt.qty, bdt.rate, bdt.amount
		)
		.where(
			(bdt.docstatus == 1) &
			(bbt.budget_kebun_tahunan == tahun_budget) &
			(bbt.divisi == divisi) &
			(bdt.item == kendaraan) 
		)
		.groupby(bdt.item)
	).run(as_dict=True)

	return list_biaya_bengkel

