
import frappe
from frappe.utils import today,flt
from frappe.model.document import Document
from frappe import _

class PengakuanPembelianTBS(Document):
	@frappe.whitelist()
	def get_timbangan(self):
		data_timbangan = frappe.db.sql("""
			select t.name as timbangan, ti.item_code, ti.item_name,(ti.netto - (t.potongan_sortasi / 100) ) as qty
			from `tabTimbangan` t
			join `tabTimbangan Item` ti on ti.parent = t.name
			where t.posting_date = %s and t.receive_type = "TBS Eksternal" and t.docstatus = 1 and supplier = %s
		""",[today(),self.nama_supplier],as_dict=True)

		self.items = []
		for row in data_timbangan:
			child = self.append("items")
			child.update(row)
			child.rate = flt(self.harga)
			child.total = flt(child.qty) * flt(child.rate)

@frappe.whitelist()
def get_rate(jarak):
	return frappe.get_value("Item Price",{"item_code":"TBS","price_list": jarak},["price_list_rate"])