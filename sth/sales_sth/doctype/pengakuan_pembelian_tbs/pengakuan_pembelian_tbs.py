
import frappe
from frappe.utils import today,flt
from frappe.model.document import Document
from frappe import _
from frappe.model.mapper import get_mapped_doc

class PengakuanPembelianTBS(Document):
	# @frappe.whitelist()
	# def get_timbangan(self):

	# 	gabungan = frappe.db.sql("""
	# 		SELECT 
	# 			gs.supplier, g.tonase_untuk_dapat_insentif, g.insentif
	# 		FROM `tabTBS Gabungan Setting` g
	# 		JOIN `tabTBS Gabungan Supplier` gs ON gs.parent = g.name
	# 		WHERE g.name = (
	# 			SELECT parent 
	# 			FROM `tabTBS Gabungan Supplier` 
	# 			WHERE supplier = %s 
	# 			LIMIT 1
	# 		)
	# 	""", [self.nama_supplier], as_dict=True)

	# 	if gabungan:
	# 		supplier_list = tuple(row.supplier for row in gabungan)
	# 		tonase_target = gabungan[0].tonase_untuk_dapat_insentif
	# 		insentif = gabungan[0].insentif
	# 	else:
	# 		supplier_list = (self.nama_supplier,)
	# 		tonase_target = 0
	# 		insentif = 0

	# 	data_timbangan = frappe.db.sql("""
	# 		select 
			
	# 		t.name as no_tiket, 
	# 		t.no_polisi as kendaraan, 
	# 		t.kode_barang as item_code, 
	# 		t.nama_barang as item_name,
	# 		(t.netto * (t.potongan_sortasi / 100) ) as pot,
	# 		t.bruto as bruto,
	# 		t.tara as tarra,
	# 		t.netto as netto,
	# 		t.netto - (t.netto * (t.potongan_sortasi / 100) ) as terima,
	# 		"Tidak" as status_pajak_pph_22,
	# 		0.25 as percent_pajak_pph_22

	# 		from `tabTimbangan` t
	# 		where 
	# 		t.posting_date = %s 
	# 		and t.receive_type = "TBS Eksternal"
	# 		and t.docstatus = 1 
	# 		AND t.supplier IN %s
	# 	""", [self.tanggal_timbangan,supplier_list], as_dict=True)

	# 	total_terima = sum(flt(row.terima) for row in data_timbangan)
	# 	# subsidi_angkut = insentif if total_terima >= tonase_target else 0
	# 	bonus = insentif if total_terima >= tonase_target else 0

	# 	self.items = []
	# 	for row in data_timbangan:
	# 		child = self.append("items")
	# 		child.update(row)
	# 		child.bonus = bonus
	# 		child.rate = flt(self.harga)
	# 		# child.total_seluruhnya = (flt(child.terima) * flt(child.rate)) + (child.subsidi_angkut * child.terima)
	# 		child.total_seluruhnya = (flt(child.rate) + flt(child.bonus) + flt(child.subsidi_angkut)) * (child.terima)
	# 		child.rupiah_pajak_pph_22 = child.total_seluruhnya * child.percent_pajak_pph_22 / 100
	# 		child.total = child.total_seluruhnya - child.rupiah_pajak_pph_22

	@frappe.whitelist()
	def get_timbangan(self):

		self.check_duplicate_submit()

		parent = None
		is_all_supplier = False

		parent_data = frappe.db.sql("""
			SELECT name
			FROM `tabTBS Gabungan Setting`
			WHERE unit = %s
			AND all_supplier = 1
			LIMIT 1
		""", (self.unit,), as_dict=True)

		if parent_data:
			parent = parent_data[0].name
			is_all_supplier = True

		if not parent:
			parent_data = frappe.db.sql("""
				SELECT s.parent
				FROM `tabTBS Gabungan Supplier` s
				INNER JOIN `tabTBS Gabungan Setting` p
					ON s.parent = p.name
				WHERE s.supplier = %s
				AND p.unit = %s
				LIMIT 1
			""", (self.nama_supplier, self.unit), as_dict=True)

			if parent_data:
				parent = parent_data[0].parent

		supplier_list = None

		if parent:

			if is_all_supplier:
				supplier_list = (self.nama_supplier,)

			else:
				suppliers = frappe.get_all(
					"TBS Gabungan Supplier",
					filters={"parent": parent},
					pluck="supplier"
				)

				if suppliers:
					supplier_list = tuple(suppliers)
				else:
					supplier_list = ("__no_supplier__",)

		else:
			supplier_list = (self.nama_supplier,)

		insentif_tiers = []

		if parent:

			if self.jarak_ring:
				insentif_tiers = frappe.db.sql("""
					SELECT tonase_untuk_dapat_insentif, insentif
					FROM `tabTBS Gabungan Insentif`
					WHERE parent = %s
					AND (ring = %s OR ring IS NULL OR ring = '')
					ORDER BY tonase_untuk_dapat_insentif DESC
				""", (parent, self.jarak_ring), as_dict=True)

			else:
				insentif_tiers = frappe.db.sql("""
					SELECT tonase_untuk_dapat_insentif, insentif
					FROM `tabTBS Gabungan Insentif`
					WHERE parent = %s
					AND (ring IS NULL OR ring = '')
					ORDER BY tonase_untuk_dapat_insentif DESC
				""", (parent,), as_dict=True)

		# conditions = """
		# 	t.posting_date = %s
		# 	AND t.receive_type = "TBS Eksternal"
		# 	AND t.docstatus = 1
		# """

		# params = [self.tanggal_timbangan]

		# if supplier_list:
		# 	conditions += " AND t.supplier IN %s"
		# 	params.append(supplier_list)

		# data_timbangan = frappe.db.sql(f"""
		# 	SELECT 
		# 		t.name as no_tiket, 
		# 		t.no_polisi as kendaraan, 
		# 		t.kode_barang as item_code, 
		# 		t.nama_barang as item_name,
		# 		(t.netto * (t.potongan_sortasi / 100)) as pot,
		# 		t.bruto as bruto,
		# 		t.tara as tarra,
		# 		t.netto as netto,
		# 		t.netto - (t.netto * (t.potongan_sortasi / 100)) as terima,
		# 		"Tidak" as status_pajak_pph_22,
		# 		0.25 as percent_pajak_pph_22
		# 	FROM `tabTimbangan` t
		# 	WHERE {conditions}
		# """, params, as_dict=True)

		# total_terima = sum(flt(row.terima) for row in data_timbangan)

		# =============================
		# QUERY UNTUK HITUNG TOTAL (GABUNGAN SUPPLIER)
		# =============================

		conditions_total = """
			t.posting_date = %s
			AND t.receive_type = "TBS Eksternal"
			AND t.docstatus = 1
		"""

		params_total = [self.tanggal_timbangan]

		print("SUPPLIER LIST:", supplier_list)

		if supplier_list:
			conditions_total += " AND t.supplier IN %s"
			params_total.append(supplier_list)

		total_rows = frappe.db.sql(f"""
			SELECT 
				t.netto - (t.netto * (t.potongan_sortasi / 100)) as terima
			FROM `tabTimbangan` t
			WHERE {conditions_total}
		""", params_total, as_dict=True)

		total_terima = sum(flt(row.terima) for row in total_rows)

		conditions_display = """
			t.posting_date = %s
			AND t.receive_type = "TBS Eksternal"
			AND t.docstatus = 1
			AND t.supplier = %s
		"""

		params_display = [self.tanggal_timbangan, self.nama_supplier]

		data_timbangan = frappe.db.sql(f"""
			SELECT 
				t.name as no_tiket, 
				t.no_polisi as kendaraan, 
				t.kode_barang as item_code, 
				t.nama_barang as item_name,
				ROUND(t.netto * (t.potongan_sortasi / 100), 0) as pot,
				t.bruto as bruto,
				t.tara as tarra,
				t.netto as netto,
				t.netto - ROUND((t.netto * (t.potongan_sortasi / 100)), 0) as terima,
				"Tidak" as status_pajak_pph_22,
				0.25 as percent_pajak_pph_22
			FROM `tabTimbangan` t
			WHERE {conditions_display}
		""", params_display, as_dict=True)

		bonus = 0

		for tier in insentif_tiers:
			if total_terima >= flt(tier.tonase_untuk_dapat_insentif):
				bonus = flt(tier.insentif)
				break

		self.items = []

		for row in data_timbangan:
			child = self.append("items")
			child.update(row)

			child.bonus = bonus
			child.rate = flt(self.harga)

			child.total_seluruhnya = (
				flt(child.rate)
				+ flt(child.bonus)
				+ flt(child.subsidi_angkut)
			) * flt(child.terima)

			child.rupiah_pajak_pph_22 = (
				child.total_seluruhnya
				* child.percent_pajak_pph_22
				/ 100
			)

			child.total = child.total_seluruhnya - child.rupiah_pajak_pph_22

	def recalc_items(self):
		for row in self.items:
			row.total_seluruhnya = (flt(row.rate) + flt(row.bonus) + flt(row.subsidi_angkut)) * flt(row.terima)
			row.rupiah_pajak_pph_22 = row.total_seluruhnya * flt(row.percent_pajak_pph_22) / 100
			row.total = row.total_seluruhnya - row.rupiah_pajak_pph_22

	def validate(self):
		self.recalc_items()
		self.calculate_parent_totals()
		self.check_duplicate_submit()

	def check_duplicate_submit(self):
		existing = frappe.db.get_value(
			"Pengakuan Pembelian TBS",
			{
				"tanggal_timbangan": self.tanggal_timbangan,
				"nama_supplier": self.nama_supplier,
				"unit": self.unit,
				"jarak_ring": self.jarak_ring,
				"docstatus": 1,
				"name": ["!=", self.name]  
			},
			"name"
		)

		if existing:
			frappe.throw(
				f"Pengakuan Pembelian TBS untuk kombinasi ini sudah disubmit di dokumen: <b>{existing}</b>"
			)

	def calculate_parent_totals(self):
		total_bruto = 0
		total_tarra = 0
		total_netto = 0
		total_potkg = 0
		total_terima = 0
		total_bonus = 0
		total_seluruhnya = 0
		total_pembayaran = 0
		total_pajak_pph_22 = 0

		for row in self.items:
			total_bruto += flt(row.bruto)
			total_tarra += flt(row.tarra)
			total_netto += flt(row.netto)
			total_potkg += flt(row.pot)
			total_terima += flt(row.terima)
			total_bonus += flt(row.bonus)*flt(row.terima)
			total_seluruhnya += flt(row.total_seluruhnya)
			total_pembayaran += flt(row.total)
			total_pajak_pph_22 += flt(row.rupiah_pajak_pph_22)

		self.total_bruto = total_bruto
		self.total_tarra = total_tarra
		self.total_netto = total_netto
		self.total_potkg = total_potkg
		self.total_terima = total_terima
		self.total_bonus = total_bonus
		self.total_seluruhnya = total_seluruhnya
		self.total_pembayaran_ke_supplier = total_pembayaran
		self.total_pajak_pph_22 = total_pajak_pph_22


@frappe.whitelist()
def get_rate(jarak):
	return frappe.get_value("Item Price",{"item_code":"TBS","price_list": jarak},["price_list_rate"])

@frappe.whitelist()
def make_purchase_invoice(source_name, target_doc=None):
	
	def set_missing_values(source, target):
		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")
	
	def update_item(source, target, source_parent):
		target.qty = source.qty
		target.rate = source.rate
		
	doclist = get_mapped_doc(
		"Pengakuan Pembelian TBS",
		source_name,
		{
			"Pengakuan Pembelian TBS": {
				"doctype": "Purchase Invoice",
				"field_map": {
					"nama_supplier": "supplier",
					"unit": "unit",
				},
				"validation": {
					"docstatus": ["=", 1]
				}
			},
			"Pengakuan Pembelian TBS Item": {  # Child table name
				"doctype": "Purchase Invoice Item",
				"field_map": {
					"item_code": "item_code",
					"item_name": "item_name",
					"qty": "qty",
					"uom": "uom",
					"rate": "rate",
					"amount": "amount",
					# Add other item field mappings
					# "warehouse": "warehouse",
					# "expense_account": "expense_account",
				},
				"postprocess": update_item
			}
		},
		target_doc,
		set_missing_values
	)
	
	return doclist


def test():
	doc = frappe.get_doc("Pengakuan Pembelian TBS", "20260310/ABAM/7222")
	doc.get_timbangan()

