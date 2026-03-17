# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_days,today

class DataTBS(Document):
	def validate(self):
		pass

	@frappe.whitelist()
	def get_data(self):
		data_lori = frappe.db.sql("""
			select 
				tbs_olah as jumlah_lori_olah,
				tbs_mentah as jumlah_lori_mentah,
				jumlah_restan_tbs_masak as jumlah_lori_masak,
				jumlah_loading_ramp as lori_estimasi_loading_ramp,
				(tbs_olah + tbs_mentah + jumlah_restan_tbs_masak + jumlah_loading_ramp) as grand_total_lori
			from `tabMonitoring TBS Olah` mto
			where mto.docstatus = 1 and tgl = %s
		""",(self.tanggal_produksi),as_dict=True)
		data_lori = data_lori[0] if data_lori else {}
		self.update(data_lori)

		self.jumlah_tbs_restan = get_total_restan(self.tanggal_produksi)
		self.jumlah_tbs_diterima = get_total_tbs(self.tanggal_produksi)
		self.grand_total_tbs = self.jumlah_tbs_restan + self.jumlah_tbs_diterima

		self.berat_rata_rata_tbs = self.grand_total_tbs / self.grand_total_lori if self.grand_total_lori else 0
		self.tbs_olah = self.berat_rata_rata_tbs * self.jumlah_lori_olah
		self.tbs_restan = self.berat_rata_rata_tbs * (self.jumlah_lori_mentah + self.jumlah_lori_masak)
		self.tbs_loading_ramp = self.berat_rata_rata_tbs * self.lori_estimasi_loading_ramp
		self.total_jam_olah = frappe.db.get_value("CBC Monitoring",{"docstatus": 1, "posting_date": self.tanggal_produksi},"total_hour_meter")
		self.kapasitas_pabrik = self.tbs_olah / self.total_jam_olah / 1000

def get_total_tbs(tanggal):
	query = frappe.db.sql("""
		select sum(balance_qty) as qty from `tabTBS Ledger Entry` tle
		where tle.item_code = 'TBS' and tle.is_cancelled = 0 and tle.type LIKE 'TBS%%' and tle.posting_date = %s
		group by tle.item_code
	""",(tanggal),as_dict=True)

	return query[0].qty if query else 0

def get_total_restan(tanggal):
	tanggal = add_days(tanggal,-1)

	query = frappe.db.sql("""
		select (tbs_restan + tbs_loading_ramp) as qty from `tabData TBS` dtb
		where dtb.tanggal = %s
	""",(tanggal),as_dict=True)

	return query[0].qty if query else 0