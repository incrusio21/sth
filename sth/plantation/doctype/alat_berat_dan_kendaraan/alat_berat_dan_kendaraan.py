# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime


def get_latest_kmhm(kendaraan, exclude=None):
	"""Cari record kmhm_akhir paling baru dari BKM Traksi & BKM Bengkel (docstatus < 2)."""
	if not kendaraan:
		return None

	conditions_traksi = "kendaraan = %(kendaraan)s AND docstatus < 2"
	conditions_bengkel = "kd_kndr = %(kendaraan)s AND docstatus < 2"
	values = {"kendaraan": kendaraan}

	if exclude:
		conditions_traksi += " AND name != %(exclude)s"
		conditions_bengkel += " AND name != %(exclude)s"
		values["exclude"] = exclude

	result = frappe.db.sql(f"""
		SELECT kmhm_akhir, sort_dt, creation FROM (
			SELECT kmhm_akhir, posting_datetime AS sort_dt, creation
			FROM `tabBuku Kerja Mandor Traksi`
			WHERE {conditions_traksi}

			UNION ALL

			SELECT kmhm_akhir, CONCAT(posting_date, ' 23:59:59') AS sort_dt, creation
			FROM `tabBuku Kerja Mandor Bengkel`
			WHERE {conditions_bengkel}
		) t
		ORDER BY sort_dt DESC, creation DESC
		LIMIT 1
	""", values, as_dict=True)

	return result[0] if result else None


@frappe.whitelist()
def sync_kmhm_akhir(kendaraan, candidate_kmhm_akhir=None, candidate_sort_dt=None, exclude=None):
	"""Set ulang kmhm_akhir kendaraan berdasarkan BKM Traksi/Bengkel terbaru.

	`candidate_*` dipakai untuk menyertakan dokumen yang sedang disimpan tapi
	belum tercermin di database (mis. saat masih di dalam validate()).
	"""
	latest = get_latest_kmhm(kendaraan, exclude=exclude)

	best_value = latest.kmhm_akhir if latest else None
	best_sort = latest.sort_dt if latest else None

	if candidate_kmhm_akhir is not None and candidate_sort_dt:
		if not best_sort or get_datetime(candidate_sort_dt) >= get_datetime(best_sort):
			best_value = candidate_kmhm_akhir
			best_sort = candidate_sort_dt

	frappe.db.set_value("Alat Berat Dan Kendaraan", kendaraan, "kmhm_akhir", best_value or 0)
	return best_value


class AlatBeratDanKendaraan(Document):

	def after_insert(self):
		self.make_cost_center()

	def on_update(self):
		self.make_cost_center()

	def make_cost_center(self):
		if not self.name or not self.company:
			return

		if frappe.db.exists(
			"Cost Center",
			{"cost_center_name": self.name, "company": self.company}
		):
			self.cost_center = "{} - {}".format(self.name, frappe.get_doc("Company", self.company).abbr)
			frappe.db.commit()
			return

		company_doc = frappe.get_doc("Company", self.company)

		root_parent = f"{company_doc.company_name} - {company_doc.abbr}"
		vra_parent = f"VRA - {company_doc.abbr}"

		if not frappe.db.exists("Cost Center", vra_parent):
			parent = frappe.new_doc("Cost Center")
			parent.cost_center_name = "VRA"
			parent.parent_cost_center = root_parent
			parent.company = self.company
			parent.is_group = 1
			parent.flags.ignore_permissions = True
			parent.insert()

		cc = frappe.new_doc("Cost Center")
		cc.cost_center_name = self.name
		cc.parent_cost_center = vra_parent
		cc.company = self.company
		cc.is_group = 0
		cc.flags.ignore_permissions = True
		cc.insert()

		self.cost_center = cc.name
		frappe.db.commit()
