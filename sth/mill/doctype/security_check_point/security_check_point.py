# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document
from frappe.desk.reportview import get_filters_cond, get_match_cond
from erpnext.controllers.queries import get_fields

class SecurityCheckPoint(Document):

	def before_insert(self):
		self.map_api_spb_trans_no()

	def map_api_spb_trans_no(self):
		"""Field spb dari API berisi trans_no SPB, bukan nama dokumennya.

		Nilai asli disimpan di spb_trans_no, lalu spb diisi nama dokumen SPB supaya
		timbangan bisa menarik nomornya lewat Security Check Point ini
		(get_spb_available menyambung lewat scp.spb = spb.name).

		Dijalankan di before_insert, bukan validate, karena _validate_links()
		jalan lebih dulu daripada validate: selama field spb masih berisi
		trans_no di titik itu, insert ditolak "Could not find SPB".
		"""
		if not (self.owner and "api@sth" in self.owner and self.spb):
			return

		trans_no = self.spb

		self.spb_trans_no = trans_no
		self.spb = self.get_or_create_spb(trans_no)

	def get_or_create_spb(self, trans_no):
		"""Nama dokumen SPB untuk trans_no ini, dibuatkan dulu kalau belum ada.

		SPB baru dibuat sebagai draft tanpa detail blok — cukup sebagai pegangan
		nomor buat timbangan. Data panennya menyusul lewat API SPB, yang memakai
		trans_no yang sama sehingga jatuh ke dokumen ini juga.
		"""
		spb_name = frappe.db.get_value("Surat Pengantar Buah", {"trans_no": trans_no}, "name")
		if spb_name:
			return spb_name

		from sth.plantation.doctype.surat_pengantar_buah.surat_pengantar_buah import create_or_update

		doc = create_or_update(
			trans_no=trans_no,
			company=self.company,
			unit=self.unit,
			divisi=self.divisi,
			posting_date=self.tanggal_panen or self.posting_date,
		)

		return doc.name

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def delivery_order_query(doctype, txt, searchfield, start, page_len, filters):
	params = {"txt": "%%%s%%" % txt, "_txt": txt.replace("%", ""), "start": start, "page_len": page_len}
	fields = get_fields(doctype, ["name"])
	conditions = []
	scond = ""

	searchfields = frappe.get_meta(doctype).get_search_fields()
	searchfields = " or ".join(f"`tabDelivery Order`.{field} like %(txt)s" for field in searchfields)

	fields = [f"`tabDelivery Order`.{r}" for r in fields]
	fields = ", ".join(fields)
	
	if filters.get('driver'):
		scond += " AND dot.driver = %(driver)s"
		params["driver"] = filters.get('driver')
		filters.pop("driver")

	fcond = get_filters_cond(doctype, filters, conditions)

	
	return frappe.db.sql(f"""
		select {fields} from `tabDelivery Order`
		join `tabDelivery Order Transporter` dot on dot.parent = `tabDelivery Order`.name
		where (`tabDelivery Order`.name like %(txt)s or {searchfields}) {fcond} {scond}
		order by
			(case when locate(%(_txt)s, `tabDelivery Order`.name) > 0 then locate(%(_txt)s, `tabDelivery Order`.name) else 99999 end),
			`tabDelivery Order`.name
		limit %(page_len)s offset %(start)s
		""",params,debug=True
	)
