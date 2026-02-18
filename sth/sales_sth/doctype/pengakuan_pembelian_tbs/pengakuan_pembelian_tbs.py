
import frappe
from frappe.utils import today,flt
from frappe.model.document import Document
from frappe import _
from frappe.model.mapper import get_mapped_doc

class PengakuanPembelianTBS(Document):
	@frappe.whitelist()
	def get_timbangan(self):

		gabungan = frappe.db.sql("""
			SELECT 
				gs.supplier
			FROM `tabTBS Gabungan Setting` g
			JOIN `tabTBS Gabungan Supplier` gs ON gs.parent = g.name
			WHERE g.name = (
				SELECT parent 
				FROM `tabTBS Gabungan Supplier` 
				WHERE supplier = %s 
				LIMIT 1
			)
		""", [self.nama_supplier], as_dict=True)

		if gabungan:
			supplier_list = tuple(row.supplier for row in gabungan)
		else:
			supplier_list = (self.nama_supplier,)

		data_timbangan = frappe.db.sql("""
			select 
			
			t.name as no_tiket, 
			t.no_polisi as kendaraan, 
			t.kode_barang as item_code, 
			t.nama_barang as item_name,
			(t.netto * (t.potongan_sortasi / 100) ) as pot,
			t.bruto as bruto,
			t.tara as tarra,
			t.netto as netto,
			t.netto - (t.netto * (t.potongan_sortasi / 100) ) as terima,
			10 as subsidi_angkut,
			"Tidak" as status_pajak_pph_22,
			0.25 as percent_pajak_pph_22

			from `tabTimbangan` t
			where 
			t.posting_date = %s 
			and t.receive_type = "TBS Eksternal"
			and t.docstatus = 1 
			AND t.supplier IN %s
		""", [self.tanggal_timbangan,supplier_list], as_dict=True, debug=1)

		self.items = []
		for row in data_timbangan:
			child = self.append("items")
			child.update(row)
			child.rate = flt(self.harga)

			child.total_seluruhnya = (flt(child.terima) * flt(child.rate)) + (child.subsidi_angkut * child.terima)
			child.rupiah_pajak_pph_22 = child.total_seluruhnya * child.percent_pajak_pph_22 / 100
			child.total = child.total_seluruhnya - child.rupiah_pajak_pph_22


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