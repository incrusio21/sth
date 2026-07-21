# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

ITEM_FIELDS = [
	"name",
	"item_name",
	"kelompok_barang",
	"nama_kelompok_barang",
	"item_group",
	"nama_sub_kelompok_barang",
	"stock_uom",
	"description",
	"status",
	"owner",
	"creation",
	"modified_by",
	"modified",
]

ITEM_GROUP_FIELDS = [
	"name",
	"item_group_name",
	"deskripsi",
	"status",
	"owner",
	"creation",
	"modified_by",
	"modified",
]


class APIEPCSSettings(Document):
	pass


def _get_kelompok_barang(table_fieldname, value_fieldname):
	settings = frappe.get_single("API EPCS Settings")
	rows = settings.get(table_fieldname) or []
	return list({r.get(value_fieldname) for r in rows if r.get(value_fieldname)})


def _get_item_list(kelompok_barang):
	if not kelompok_barang:
		return []
	return frappe.get_all(
		"Item",
		fields=ITEM_FIELDS,
		filters=[["kelompok_barang", "in", kelompok_barang]],
		limit_page_length=0,
	)


def _get_item_group_list(kelompok_barang):
	if not kelompok_barang:
		return []
	return frappe.get_all(
		"Item Group",
		fields=ITEM_GROUP_FIELDS,
		filters=[["parent_item_group", "in", kelompok_barang]],
		limit_page_length=0,
	)


@frappe.whitelist(allow_guest=True)
def get_item_bibit():
	return _get_item_list(_get_kelompok_barang("bibit", "kelompok_bibit"))


@frappe.whitelist(allow_guest=True)
def get_kelompok_bibit():
	return _get_item_group_list(_get_kelompok_barang("bibit", "kelompok_bibit"))


@frappe.whitelist(allow_guest=True)
def get_item_material():
	return _get_item_list(_get_kelompok_barang("material", "kelompok_material"))


@frappe.whitelist(allow_guest=True)
def get_kelompok_material():
	return _get_item_group_list(_get_kelompok_barang("material", "kelompok_material"))

@frappe.whitelist(allow_guest=True)
def get_item_apd():
	return _get_item_list(_get_kelompok_barang("apd", "daftar_apd"))

@frappe.whitelist(allow_guest=True)
def get_kelompok_apd():
	return _get_item_group_list(_get_kelompok_barang("apd", "daftar_apd"))

@frappe.whitelist(allow_guest=True)
def get_security_transaction_type():
	data = frappe.get_all(
		"Transaction Type",
		fields=["name", "field_di_security_check_point", "transaction_type"],
		limit_page_length=0,
	)
	return {"data": data}