# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import scrub, unscrub
from frappe.desk.reportview import get_filters_cond, get_match_cond
from frappe.permissions import has_permission
from frappe.utils import cint, nowdate, unique

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
	ignore_user_permissions: bool = True,
):
	doctype = "Kegiatan"
	doctype_child = "Kegiatan Company"
	conditions = []
	fields = get_fields(doctype, ["name", "nm_kgt"])
	ignore_permissions = True
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
				"fcondchild": get_filters_cond(doctype_child, filters_child, conditions, ignore_permissions=True) if filters_child else "",
				"mcond": mcond,
			}
		),
		{"txt": "%%%s%%" % txt, "_txt": txt.replace("%", ""), "start": start, "page_len": page_len}
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def material_kegiatan_query(
	doctype,
	txt,
	searchfield,
	start,
	page_len,
	filters,
	as_dict=False
):
	doctype = "Item"
	doctype_child = "Kegiatan Material"

	conditions = []
	filters_child = {}

	if isinstance(filters, str):
		filters = json.loads(filters)
		
	# Get searchfields from meta and use in Item Link field query
	meta = frappe.get_meta(doctype, cached=True)
	searchfields = meta.get_search_fields()

	columns = ""
	extra_searchfields = [field for field in searchfields if field not in ["name", "description"]]

	if extra_searchfields:
		columns += ", " + ", ".join(extra_searchfields)

	if "description" in searchfields:
		columns += """, if(length(tabItem.description) > 40, \
			concat(substr(tabItem.description, 1, 40), "..."), description) as description"""

	searchfields = searchfields + [
		field
		for field in [searchfield or "name", "item_code", "item_group", "item_name"]
		if field not in searchfields
	]
	searchfields = " or ".join(["`tabItem`." + field + " like %(txt)s" for field in searchfields])

	description_cond = ""
	if frappe.db.count(doctype, cache=True) < 50000:
		# scan description only if items are less than 50000
		description_cond = "or tabItem.description LIKE %(txt)s"

	if filters and isinstance(filters, dict):
		if filters.get("kegiatan"):
			filters_child["kegiatan"] = filters["kegiatan"]
			del filters["kegiatan"]
		else:
			filters.pop("kegiatan", None)

	return frappe.db.sql(
		"""select
			tabItem.name {columns}
		from tabItem
		join `tabKegiatan Material` on `tabKegiatan Material`.item_code = `tabItem`.name
		where tabItem.docstatus < 2
			and tabItem.disabled=0
			and tabItem.has_variants=0
			and (tabItem.end_of_life > %(today)s or ifnull(tabItem.end_of_life, '0000-00-00')='0000-00-00')
			and ({scond} or tabItem.item_code IN (select parent from `tabItem Barcode` where barcode LIKE %(txt)s)
				{description_cond})
			{fcond} {mcond}
		order by
			if(locate(%(_txt)s, tabItem.name), locate(%(_txt)s, tabItem.name), 99999),
			if(locate(%(_txt)s, item_name), locate(%(_txt)s, item_name), 99999),
			tabItem.idx desc,
			tabItem.name, item_name
		limit %(start)s, %(page_len)s """.format(
			columns=columns,
			scond=searchfields,
			fcond=get_filters_cond(doctype, filters, conditions).replace("%", "%%"),
			fcondchild=get_filters_cond(doctype_child, filters_child, conditions, ignore_permissions=True) if filters_child else "",
			mcond=get_match_cond(doctype).replace("%", "%%"),
			description_cond=description_cond,
		),
		{
			"today": nowdate(),
			"txt": "%%%s%%" % txt,
			"_txt": txt.replace("%", ""),
			"start": start,
			"page_len": page_len,
		},
		as_dict=as_dict,
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

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def month_query(
	doctype,
	txt,
	searchfield,
	start,
	page_len,
	filters,
	reference_doctype: str | None = None,
	ignore_user_permissions: bool = True,
):
	doctype = "Months"
	conditions = []
	fields = get_fields(doctype, ["name", "month_number"])
	ignore_permissions = True
	filters = filters or {}

	if reference_doctype and ignore_user_permissions:
		ignore_permissions = has_ignored_field(reference_doctype, doctype) and has_permission(
			doctype,
			ptype="select" if frappe.only_has_select_perm(doctype) else "read",
		)

	mcond = "" if ignore_permissions else get_match_cond(doctype)
	
	return frappe.db.sql(
		"""select {fields} from `tabMonths`
		where ({key} like %(txt)s or month_number like %(txt)s)
			{fcond} {mcond}
		order by
			(case when locate(%(_txt)s, name) > 0 then locate(%(_txt)s, name) else 99999 end),
			idx desc, month_number asc
		limit %(page_len)s offset %(start)s""".format(
			**{
				"fields": ", ".join(fields),
				"key": searchfield,
				"fcond": get_filters_cond(doctype, filters, conditions) if filters else "",
				"mcond": mcond,
			}
		),
		{"txt": "%%%s%%" % txt, "_txt": txt.replace("%", ""), "start": start, "page_len": page_len}
	)

def get_fields(doctype, fields=None):
	if fields is None:
		fields = []
	meta = frappe.get_meta(doctype)
	fields.extend(meta.get_search_fields())

	if meta.title_field and meta.title_field.strip() not in fields:
		fields.insert(1, meta.title_field.strip())
	
	return unique([f"`tab{doctype}`.{f}" for f in fields])