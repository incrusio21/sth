# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc

class PengeluaranBarang(Document):
	def validate(self):
		self.validate_qty()

	def on_submit(self):
		self.create_ste()
		self.update_items_out()
	
	def on_cancel(self):
		if frappe.db.exists("Stock Entry",{"references": self.name}):
			ste = frappe.get_doc("Stock Entry",{"references": self.name})
			ste.cancel()

	def validate_qty(self):
		for row in self.items:
			jumlah_permintaan,jumlah_keluar = frappe.db.get_value("Permintaan Pengeluaran Barang Item",row.reference,["jumlah","jumlah_keluar"])
			
			if row.jumlah > jumlah_permintaan - jumlah_keluar:
				frappe.throw((f"Jumlah barang melebihi permintaan: {row.jumlah}"))
			
			if row.jumlah > row.jumlah_saat_ini:
				frappe.throw((f"Jumlah barang {row.item_name} melebihi stock saat ini: {row.jumlah_saat_ini - row.jumlah}"))

	def update_items_out(self):
		for row in self.items:
			jumlah_keluar = frappe.db.get_value("Permintaan Pengeluaran Barang Item",row.reference,"jumlah_keluar")
			frappe.db.set_value("Permintaan Pengeluaran Barang Item",row.reference,"jumlah_keluar",jumlah_keluar + row.jumlah,update_modified=False)
		
		frappe.get_doc("Permintaan Pengeluaran Barang",self.no_permintaan_pengeluaran).update_status()


	def update_return_percentage(self):
		qty = 0
		return_qty = 0

		for row in self.items:
			qty += row.jumlah
			return_qty += row.jumlah_retur
		
		return_percent = return_qty/qty * 100

		self.db_set("return_percentage",return_percent)

	@frappe.whitelist()
	def set_items(self):
		self.items = []
		if not self.validate_document_permintaan():
			return

		items = frappe.get_all("Permintaan Pengeluaran Barang Item",{"parent":self.no_permintaan_pengeluaran},["kode_barang","satuan","(jumlah - jumlah_keluar) as jumlah","jumlah_saat_ini","kendaraan","km","kegiatan","nama_kegiatan","sub_unit","blok","name as reference"])

		for row in items:
			child = self.append("items",row)
			child.item_name = frappe.get_cached_value("Item",row.kode_barang,"item_name")

	def validate_document_permintaan(self):
		company,status,outgoing = frappe.db.get_value("Permintaan Pengeluaran Barang",self.no_permintaan_pengeluaran, ["pt_pemilik_barang","status","outgoing"])
		if company != self.pt_pemilik_barang or status == "Closed" or outgoing == 100:
			return False
		return True

	def create_ste(self):
		def postprocess(source,target):
			target.stock_entry_type = "Material Issue"
			
			update_fields = (
				"item_name",
				"stock_uom",
				"description",
				"expense_account",
				"cost_center",
				"conversion_factor",
				"barcode",
			)

			akun_expense = ""
			procurement_settings = frappe.get_single("Procurement Settings")
			
			for row in procurement_settings.akun_pengeluaran_table:
				if row.company == self.company:
					akun_expense = row.akun_pengeluaran

			for item in target.items:
				item_details = target.get_item_details(
					frappe._dict(
						{
							"item_code": item.item_code,
							"company": target.company,
							"project": target.project,
							"uom": item.uom,
							"s_warehouse": item.s_warehouse,
							"expense_account": akun_expense
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


		def update_item(source,target,source_parent):
			target.s_warehouse = source_parent.gudang
			

		mapper = {
			"Pengeluaran Barang": {
				"doctype": "Stock Entry",
				"field_map": {
					"name":"references",
					"doctype": "reference_doctype",
					"pt_pemilik_barang":"company",
					"tanggal":"posting_date"
				}
			},

			"Pengeluaran Barang Item": {
				"doctype": "Stock Entry Detail",
				"field_map": {
					"kode_barang":"item_code",
					"jumlah": "qty",
					"kendaraan":"custom_alat_berat_dan_kendaraan",
					"satuan": "uom"
				},
				"postprocess": update_item
			}
		}

		doc = get_mapped_doc("Pengeluaran Barang",self.name,mapper,None,postprocess,True)
		doc.insert()
		doc.submit()
		
		self.ste_reference = doc.name

@frappe.whitelist()
def get_report_pemakaian_material(kode_barang):
	from erpnext.accounts.utils import get_fiscal_year
	today = frappe.utils.today()
	fiscal_year = get_fiscal_year(date=today,boolean=True)
	start_year = fiscal_year[0][1]

	return frappe.db.sql("""
		SELECT pb.name as no_transaksi, pb.tanggal , pb.gudang, pbi.sub_unit ,"" as alokasi, pbi.kendaraan ,"" as pengguna,
		pbi.kode_barang, pbi.item_name as nama_barang,pbi.km ,pbi.jumlah ,i.kode_kelompok_barang ,i.kode_sub_kelompok_barang ,
		i.nama_sub_kelompok_barang ,ig.item_group_name as kelompok_barang
		FROM `tabPengeluaran Barang` pb
		JOIN `tabPengeluaran Barang Item` pbi on pbi.parent  = pb.name 
		JOIN `tabItem` i on i.name = pbi.kode_barang 
		JOIN `tabItem Group` ig on i.kelompok_barang = ig.name
		where pb.docstatus = 1 and pbi.kode_barang = %s AND pb.tanggal BETWEEN %s AND %s
		order by pb.tanggal,pb.name
	""",(kode_barang,start_year,today),as_dict=True)

@frappe.whitelist()
def history_pemakaian_barang(asset):
	from erpnext.accounts.utils import get_fiscal_year
	today = frappe.utils.today()
	fiscal_year = get_fiscal_year(date=today,boolean=True)
	start_year = fiscal_year[0][1]

	details = frappe.db.sql("""
		select e.first_name as operator ,k.no_pol, k.name as kode_kendaraan, k.tipe_master as jenis
		from `tabAlat Berat Dan Kendaraan` k
		join `tabEmployee` e on e.name = k.operator
	    where k.no_pol = %s
	""",(asset),as_dict=True)

	details = details[0] if details else None

	query = frappe.db.sql("""
		SELECT pbi.`kode_barang`, i.`item_name` AS nama_barang, pb.`tanggal`,
		SUM(pbi.`jumlah`) AS jumlah 
		FROM `tabPengeluaran Barang Item` pbi
		JOIN `tabPengeluaran Barang` pb ON pb.`name` = pbi.`parent`
		LEFT JOIN `tabAlat Berat Dan Kendaraan` k ON pbi.`kendaraan` = k.`name`
		JOIN `tabItem` i ON i.`name` = pbi.`kode_barang`
		where pb.docstatus = 1 and k.no_pol = %s AND pb.tanggal BETWEEN %s AND %s
		GROUP BY pbi.`kode_barang`, MONTH(pb.`tanggal`)
		ORDER BY pb.`tanggal` ASC 
	""",(asset,start_year,today),as_dict=True)

	result = []
	month = []

	for data in query:
		dict_data = frappe._dict({})
		exists = next((r for r in result if r.kode_barang == data.kode_barang),None)
		date = data.tanggal.strftime("%Y-%m")
		month.append(date)

		if exists:
			exists[date] = data.jumlah
			exists.jumlah += data.jumlah
		else:
			dict_data.kode_barang = data.kode_barang
			dict_data.nama_barang = data.nama_barang
			dict_data[date] = data.jumlah
			dict_data.jumlah = data.jumlah
			result.append(dict_data)


	return {
		"details": details,
		"data" :result,
		"month": set(month)
	}