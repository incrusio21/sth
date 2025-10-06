# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import unscrub
from frappe.desk.reportview import get_filters_cond, get_match_cond
from frappe.permissions import has_permission
from frappe.utils import cint, unique

from erpnext.controllers.queries import has_ignored_field

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def kegiatan_query(
	doctype,
	txt,
	searchfield,
	start,
	page_len,
	filters,
	reference_doctype: str | None = None,
	ignore_user_permissions: bool = False,
):
	doctype = "Kegiatan"
	doctype_child = "Kegiatan Company"
	conditions = []
	fields = get_fields(doctype, ["name", "nm_kgt"])
	ignore_permissions = False
	filters = filters or {}
	filters_child = {}

	if reference_doctype and ignore_user_permissions:
		ignore_permissions = has_ignored_field(reference_doctype, doctype) and has_permission(
			doctype,
			ptype="select" if frappe.only_has_select_perm(doctype) else "read",
		)

	mcond = "" if ignore_permissions else get_match_cond(doctype)
	if filters.get("company"):
		filters_child["company"] = filters["company"]
		del filters["company"]

	if not filters.get("is_group"):
		filters["is_group"] = 0
	
	return frappe.db.sql(
		"""select {fields} from `tabKegiatan`
		join `tabKegiatan Company` on `tabKegiatan Company`.parent = `tabKegiatan`.name
		where (`tabKegiatan`.{key} like %(txt)s
				or nm_kgt like %(txt)s)
			{fcond} {mcond} {fcondchild}
		order by
			(case when locate(%(_txt)s, `tabKegiatan`.name) > 0 then locate(%(_txt)s, `tabKegiatan`.name) else 99999 end),
			(case when locate(%(_txt)s, nm_kgt) > 0 then locate(%(_txt)s, nm_kgt) else 99999 end),
			`tabKegiatan`.idx desc,
			`tabKegiatan`.name, nm_kgt
		limit %(page_len)s offset %(start)s""".format(
			**{
				"fields": ", ".join(fields),
				"key": searchfield,
				"fcond": get_filters_cond(doctype, filters, conditions) if filters else "",
				"fcondchild": get_filters_cond(doctype_child, filters_child, conditions) if filters_child else "",
				"mcond": mcond,
			}
		),
		{"txt": "%%%s%%" % txt, "_txt": txt.replace("%", ""), "start": start, "page_len": page_len}
	)


@frappe.whitelist()
def kegiatan_fetch_data(kegiatan, company, fieldname):
	if isinstance(fieldname, str):
		fieldname = json.loads(fieldname)

	return frappe.get_value("Kegiatan Company", {
		"parent": kegiatan,
		"company": company
	}, fieldname, as_dict=1)


@frappe.whitelist()
def get_rencana_kerja_harian(kode_kegiatan, divisi, blok, posting_date, is_bibitan=False):
	fieldname = "batch" if cint(is_bibitan) else "blok"

	rkh = frappe.get_value("Rencana Kerja Harian", {
		"kode_kegiatan": kode_kegiatan, "divisi": divisi, fieldname: blok, "posting_date": posting_date,
		"docstatus": 1
	}, ["name as rencana_kerja_harian", "voucher_type", "voucher_no"], as_dict=1)

	if not rkh:
		frappe.throw(""" Rencana Kerja Harian not Found for Filters <br> 
			Kegiatan : {} <br> 
			Divisi : {} <br> 
			{} : {} <br>
			Date : {} """.format(kode_kegiatan, divisi, unscrub(fieldname), blok, posting_date))

	# no rencana kerja harian
	ress = { 
		**rkh,
		"material": frappe.db.get_all("Detail RKH Material", 
			filters={"parent": rkh}, fields=["item", "uom"]
		) 
	}

	return ress

def get_fields(doctype, fields=None):
	if fields is None:
		fields = []
	meta = frappe.get_meta(doctype)
	fields.extend(meta.get_search_fields())

	if meta.title_field and meta.title_field.strip() not in fields:
		fields.insert(1, meta.title_field.strip())
	
	return unique([f"`tab{doctype}`.{f}" for f in fields])