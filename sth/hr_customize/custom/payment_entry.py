# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.permissions import has_permission
from frappe.desk.reportview import get_filters_cond, get_match_cond

from erpnext.controllers.queries import has_ignored_field

from sth.controllers.queries import get_fields
from sth.hr_customize import get_payment_settings

@frappe.whitelist()
def get_internal_employee():
	return get_payment_settings("internal_employee") or ""

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_payment_reference(
	doctype,
	txt,
	searchfield,
	start,
	page_len,
	filters,
	reference_doctype: str | None = None,
	ignore_user_permissions: bool = False,
):
	doctype = "DocType"
	conditions = []
	fields = get_fields(doctype, ["name"])
	ignore_permissions = False

	if reference_doctype and ignore_user_permissions:
		ignore_permissions = has_ignored_field(reference_doctype, doctype) and has_permission(
			doctype,
			ptype="select" if frappe.only_has_select_perm(doctype) else "read",
		)

	mcond = "" if ignore_permissions else get_match_cond(doctype)
	
	if filters.get("party_type"):
		doc_ref = []
		for d in get_payment_settings("reference"):
			if d.party_type != filters["party_type"]:
				continue
			
			doc_ref.extend(d.doctype_ref.split("\n"))

		if doc_ref:
			filters["name"] = ["in", doc_ref]

		del filters["party_type"]
		
	return frappe.db.sql(
		"""select {fields} from `tabDocType`
		where ({key} like %(txt)s like %(txt)s)
			{fcond} {mcond}
		order by
			(case when locate(%(_txt)s, name) > 0 then locate(%(_txt)s, name) else 99999 end),\
			idx desc,
			name
		limit %(page_len)s offset %(start)s""".format(
			**{
				"fields": ", ".join(fields),
				"key": searchfield,
				"fcond": get_filters_cond(doctype, filters, conditions),
				"mcond": mcond,
			}
		),
		{"txt": "%%%s%%" % txt, "_txt": txt.replace("%", ""), "start": start, "page_len": page_len},
	)