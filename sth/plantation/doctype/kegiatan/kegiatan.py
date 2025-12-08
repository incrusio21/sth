# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cstr, flt
from frappe.utils.nestedset import NestedSet


class Kegiatan(NestedSet):
	
	def autoname(self):
		self.name = get_autoname_with_number(self.kd_kgt, self.nm_kgt)

	def validate(self):
		self.validate_items_company()
		self.validate_material()

	def validate_items_company(self):
		if self.is_group:
			self.items = []
		
		if not self.have_premi:
			self.premi_type = None
			
		for d in self.items:
			# Reset premi fields if not applicable
			if not self.have_premi or self.premi_type != "Percentage":
				d.persentase_premi = d.rupiah_premi = d.min_basis_premi = 0
			else:
				d.min_basis_premi = flt(d.volume_basis * (100 + d.persentase_premi) / 100)

			# Reset day status fields if not applicable
			if not self.have_premi or self.premi_type != "Day Status":
				d.workday = d.holiday = d.workday_base = d.holiday_base = 0
			else:
				d.workday = 0 if d.workday_base else d.workday
				d.holiday = 0 if d.holiday_base else d.holiday


	def validate_material(self):
		if self.is_group:
			self.material = []

def get_autoname_with_number(number_value, doc_title):
	"""append title with prefix as number and suffix as company's abbreviation separated by '-'"""
	parts = [doc_title.strip()]

	if cstr(number_value).strip():
		parts.insert(0, cstr(number_value).strip())

	return " - ".join(parts)

@frappe.whitelist()
def get_children(doctype, parent, kategori_kegiatan=None, is_root=False):
	from erpnext.accounts.report.financial_statements import sort_accounts

	parent_fieldname = "parent_" + frappe.scrub(doctype)
	fields = ["name as value", "is_group as expandable", "kategori_kegiatan"]
	filters = [["docstatus", "<", 2]]

	filters.append([f'ifnull(`{parent_fieldname}`,"")', "=", "" if is_root else parent])

	if is_root:
		if kategori_kegiatan:
			filters.append(["kategori_kegiatan", "=", kategori_kegiatan])
	else:
		fields += [parent_fieldname + " as parent"]

	acc = frappe.get_list(doctype, fields=fields, filters=filters)

	# if doctype == "Account":
	# 	sort_accounts(acc, is_root, key="value")

	return acc