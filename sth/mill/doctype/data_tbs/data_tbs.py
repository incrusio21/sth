# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt, now
from frappe.model.mapper import get_mapped_doc

class DataTBS(Document):
	def validate(self):
		self.validate_duplikat()
		self.jumlah_tbs_restan = get_restan_awal(self.unit, self.tanggal_produksi, self.name, self.creation)
		self.calculate_totals()

	def validate_duplikat(self):
		"""Satu unit cuma boleh punya satu Data TBS per tanggal proses.

		Restan awal dirantai dari dokumen sebelumnya, jadi dua dokumen di hari
		yang sama membuat TBS diterima hari itu terhitung dua kali di restan.
		Dokumen yang dibatalkan tidak ikut dihitung, supaya amend tetap bisa.
		"""
		if not (self.unit and self.tanggal_produksi):
			return

		kembar = frappe.db.get_value("Data TBS", {
			"name": ("!=", self.name),
			"unit": self.unit,
			"tanggal_produksi": self.tanggal_produksi,
			"docstatus": ("<", 2),
		})

		if kembar:
			frappe.throw(
				"Data TBS {0} sudah memakai tanggal proses {1} untuk unit {2}.".format(
					frappe.bold(kembar), frappe.bold(self.tanggal_produksi), frappe.bold(self.unit)
				)
			)

	def on_submit(self):
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
				jumlah_loading_ramp as lori_estimasi_loading_ramp
			from `tabMonitoring TBS Olah` mto
			where mto.docstatus = 1 and tgl = %s
		""",(self.tanggal_produksi),as_dict=True)

		# Tanpa Monitoring TBS Olah lorinya dinolkan, bukan dibiarkan memakai
		# angka Get Data sebelumnya yang tanggalnya sudah lain.
		self.update(data_lori[0] if data_lori else {
			"jumlah_lori_olah": 0,
			"jumlah_lori_mentah": 0,
			"jumlah_lori_masak": 0,
			"lori_estimasi_loading_ramp": 0,
		})

		self.jumlah_tbs_restan = get_restan_awal(self.unit, self.tanggal_produksi, self.name, self.creation)
		self.jumlah_tbs_diterima = get_total_tbs(self.tanggal_produksi,self.unit)
		self.total_jam_olah = frappe.db.get_value("CBC Monitoring",{"docstatus": 1, "posting_date": self.tanggal_produksi},"total_hour_meter") or 0

		self.calculate_totals()

	def calculate_totals(self):
		"""Bagi TBS hari ini ke olah, restan, dan loading ramp menurut porsi lorinya."""
		self.grand_total_lori = (
			cint(self.jumlah_lori_olah)
			+ cint(self.jumlah_lori_mentah)
			+ cint(self.jumlah_lori_masak)
			+ cint(self.lori_estimasi_loading_ramp)
		)
		self.grand_total_tbs = flt(self.jumlah_tbs_restan) + flt(self.jumlah_tbs_diterima)

		if self.grand_total_lori:
			self.berat_rata_rata_tbs = self.grand_total_tbs / self.grand_total_lori
			self.tbs_olah = self.berat_rata_rata_tbs * cint(self.jumlah_lori_olah)
			self.tbs_restan = self.berat_rata_rata_tbs * (cint(self.jumlah_lori_mentah) + cint(self.jumlah_lori_masak))
			self.tbs_loading_ramp = self.berat_rata_rata_tbs * cint(self.lori_estimasi_loading_ramp)
		else:
			# Tidak ada lori berarti tidak ada yang diolah, jadi seluruh TBS —
			# restan awal maupun yang diterima hari itu — jadi restan hari
			# berikutnya. Membiarkan berat rata-rata nol memakainya sebagai
			# pengali bikin restannya ikut nol dan TBS-nya hilang dari rantai.
			self.berat_rata_rata_tbs = 0
			self.tbs_olah = 0
			self.tbs_restan = self.grand_total_tbs
			self.tbs_loading_ramp = 0

		self.total_tbs_restan = flt(self.tbs_restan) + flt(self.tbs_loading_ramp)
		self.kapasitas_pabrik = self.tbs_olah / self.total_jam_olah / 1000 if self.total_jam_olah else 0

	def create_ste(self):
		# Pergerakan stok TBS hari itu: yang diterima dikurangi yang diolah.
		# Sengaja tidak dibulatkan ke presisi field — total_tbs_restan presisinya
		# 0 supaya tampil bulat di form, dan memakainya di sini bikin stok
		# meleset sampai setengah kilo tiap hari. Pembulatannya diserahkan ke
		# presisi qty Stock Entry.
		selisih = flt(self.total_tbs_restan) - flt(self.jumlah_tbs_restan)

		if not flt(selisih, 3):
			return

		def postprocess(source,target):
			target.set_posting_time = 1
			target.posting_date = self.tanggal_produksi
			target.posting_time = "23:59:59"
			target.stock_entry_type = "Material Receipt" if selisih > 0 else "Material Issue"
			
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

			item = target.append("items")
			item.item_code = frappe.db.get_value("Item",{"tipe_barang": "TBS"})
			item.qty = abs(selisih)
			gudang = get_warehouse_tbs(self.unit)
			if selisih > 0:
				item.t_warehouse = gudang
			else:
				item.s_warehouse = gudang

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

def get_restan_awal(unit, tanggal_produksi, name=None, creation=None):
	"""Restan awal hari ini adalah Total TBS Restan dokumen sebelumnya.

	Diambil dari dokumennya, bukan dari saldo Bin, supaya angkanya tidak
	tergantung kapan dokumen kemarin disubmit. Bin baru bergerak waktu Data TBS
	disubmit, jadi selama dokumen kemarin masih draft saldo Bin masih saldo
	beberapa hari lalu — itu yang bikin serangkaian dokumen memakai restan awal
	yang sama waktu disubmit borongan.

	Draft ikut dihitung dengan alasan yang sama: dokumen hari ini biasanya
	disiapkan sebelum dokumen kemarin disubmit. Yang dibatalkan dilewati, jadi
	sesudah amend yang terbaca dokumen penggantinya.
	"""
	if not (unit and tanggal_produksi):
		return 0

	sebelumnya = frappe.db.sql("""
		select total_tbs_restan
		from `tabData TBS`
		where unit = %(unit)s and docstatus < 2 and name != %(name)s
			and (tanggal_produksi < %(tanggal_produksi)s
				or (tanggal_produksi = %(tanggal_produksi)s and creation < %(creation)s))
		order by tanggal_produksi desc, creation desc
		limit 1
	""", {
		"unit": unit,
		"name": name or "",
		"tanggal_produksi": tanggal_produksi,
		"creation": creation or now(),
	})

	return flt(sebelumnya[0][0]) if sebelumnya else 0

def get_warehouse_tbs(unit):
	return frappe.db.get_value("Warehouse",{"unit":unit,"warehouse_category": "TBS"})
