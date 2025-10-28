# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

# import frappe

from frappe.utils import flt
from sth.controllers.budget_controller import BudgetController


class BudgetPerawatanTahunan(BudgetController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fieldname_total.extend([
			"qty", "rotasi"
		])
		self.duplicate_param.extend([
			"divisi", "kegiatan"
		])
		self.kegiatan_fetch_if_empty_fieldname = ["rupiah_basis"]

	def validate(self):
		super().validate()
		self.set_uom_upah_perawatan()
		self.set_ha_per_tahun()

	def set_uom_upah_perawatan(self):
		for d in self.upah_perawatan:
			d.uom = self.uom

	def set_ha_per_tahun(self):
		table_field = "upah_bibitan" if self.is_bibitan else "upah_perawatan"
		self.ha_per_tahun = flt(self.grand_total / self.get(f"{table_field}_qty"), self.precision("ha_per_tahun"))

	def update_rate_or_qty_value(self, item, precision):
		if item.parentfield not in ["upah_bibitan", "upah_perawatan"]:
			return
		
		item.rate = item.get("rate") or self.rupiah_basis

	def after_calculate_item_values(self, table_fieldname, options, total):
		super().after_calculate_item_values(table_fieldname, options, total)
		table_item = self.get(table_fieldname)

		fieldname = f"mean_${table_fieldname}_rotasi"
		if not self.meta.has_field(fieldname):
			return

		self.set(fieldname, flt((total["rotasi"] / len(table_item)) if table_item else 0, self.precision(fieldname)))