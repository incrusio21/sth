# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_days,today,flt
from frappe.model.mapper import get_mapped_doc

class DataTBS(Document):
	def validate(self):
		pass

	def on_submit(self):
		if self.tbs_restan > 0 or self.jumlah_tbs_diterima > 0 :
			self.create_ste()
	
	def on_cancel(self):
		ste = frappe.db.get_all("Stock Entry",{"references": self.name})
		for row in ste:
			doc = frappe.get_doc("Stock Entry",row)
			doc.cancel()
	
	def on_trash(self):
		ste = frappe.db.get_all("Stock Entry",{"references": self.name})
		for row in ste:
			doc = frappe.get_doc("Stock Entry",row)
			doc.delete()

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

		self.jumlah_tbs_restan = get_total_restan(self.unit)
		self.jumlah_tbs_diterima = get_total_tbs(self.tanggal_produksi,self.unit)
		self.grand_total_tbs = flt(self.jumlah_tbs_restan) + flt(self.jumlah_tbs_diterima)

		self.berat_rata_rata_tbs = self.grand_total_tbs / self.grand_total_lori if self.grand_total_lori else 0
		self.tbs_olah = self.berat_rata_rata_tbs * self.jumlah_lori_olah
		self.tbs_restan = self.berat_rata_rata_tbs * (self.jumlah_lori_mentah + self.jumlah_lori_masak)
		self.tbs_loading_ramp = self.berat_rata_rata_tbs * self.lori_estimasi_loading_ramp
		self.total_tbs_restan = flt(self.tbs_restan) + flt(self.tbs_loading_ramp)

		self.total_jam_olah = frappe.db.get_value("CBC Monitoring",{"docstatus": 1, "posting_date": self.tanggal_produksi},"total_hour_meter") or 0
		self.kapasitas_pabrik = self.tbs_olah / self.total_jam_olah / 1000 if self.total_jam_olah else 0

	def create_ste(self):
		def postprocess(source,target):
			add_stock = flt(self.total_tbs_restan) > flt(self.jumlah_tbs_restan) or self.total_tbs_restan == 0

			target.stock_entry_type = "Material Receipt" if add_stock else "Material Issue"
			
			update_fields = (
				"item_name",
				"stock_uom",
				"description",
				"expense_account",
				"cost_center",
				"conversion_factor",
				"barcode",
				"uom"
			)

			# akun_expense = ""
			# procurement_settings = frappe.get_single("Procurement Settings")
			
			# for row in procurement_settings.akun_pengeluaran_table:
			# 	if row.company == self.company:
			# 		akun_expense = row.akun_pengeluaran

			item = target.append("items")
			item.item_code = frappe.db.get_value("Item",{"tipe_barang": "TBS"})
			if add_stock:
				item.qty = self.jumlah_tbs_diterima if self.total_tbs_restan == 0 else self.total_tbs_restan - self.jumlah_tbs_restan				
				item.t_warehouse = frappe.db.get_value("Warehouse",{"unit": self.unit,"warehouse_category": "TBS"})
			else:
				item.qty = self.jumlah_tbs_restan - self.total_tbs_restan
				item.s_warehouse = frappe.db.get_value("Warehouse",{"unit": self.unit,"warehouse_category": "TBS"})

			item_details = target.get_item_details(
				frappe._dict(
					{
						"item_code": item.item_code,
						"company": target.company,
						"project": target.project,
					}
				),
				for_update=True,
			)

			for field in update_fields:
				if not item.get(field):
					item.set(field, item_details.get(field))
				if field == "conversion_factor" and item.uom == item_details.get("stock_uom"):
					item.set(field, item_details.get(field))
			
			
			target.run_method("set_missing_values")
			

		mapper = {
			"Data TBS": {
				"doctype": "Stock Entry",
				"field_map": {
					"name":"references",
					"doctype": "reference_doctype",
					"tanggal":"posting_date"
				}
			},
		}

		doc = get_mapped_doc(self.doctype,self.name,mapper,None,postprocess,True)
		doc.insert()
		doc.submit()

def get_total_tbs(tanggal,unit):
	query = frappe.db.sql("""
		SELECT sum(netto_2) as qty
		FROM `tabTimbangan` t
		WHERE receive_type IN ('TBS Internal', 'TBS Eksternal') AND docstatus = 1 AND posting_date = %s AND unit = %s
	""",(tanggal,unit),as_dict=True)

	return query[0].qty if query else 0

def get_total_restan(unit):
	query = frappe.db.sql("""
		select b.actual_qty as qty from `tabBin` b
		join `tabItem` i on b.item_code = i.name
		join `tabWarehouse` w on w.name = b.warehouse
		where i.tipe_barang = 'TBS' and w.unit = %s and w.name = %s
	""",(unit,get_warehouse_tbs(unit)),as_dict=True)

	return query[0].qty if query else 0

def get_warehouse_tbs(unit):
	return frappe.db.get_value("Warehouse",{"unit":unit,"warehouse_category": "TBS"})

	