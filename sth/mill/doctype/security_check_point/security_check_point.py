# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document
from frappe.desk.reportview import get_filters_cond, get_match_cond
from erpnext.controllers.queries import get_fields

class SecurityCheckPoint(Document):

	def validate(self):
		self.map_api_spb_trans_no()

	def map_api_spb_trans_no(self):
		if not (self.owner and "api@sth" in self.owner and self.spb):
			return

		spb_name = frappe.db.get_value("Surat Pengantar Buah", {"trans_no": self.spb}, "name")

		if spb_name:
			self.spb = spb_name
		else:
			self.spb_trans_no = self.spb
			self.spb = ""

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
