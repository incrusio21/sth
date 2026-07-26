# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

"""API untuk menarik data dari doctype Timbangan."""

from datetime import datetime, time as dtime, timedelta

import frappe
from frappe import _
from frappe.utils import get_datetime, getdate

TIMBANGAN_FIELDS = [
	"name",
	"unit",
	"trans_no",
	"posting_date",
	"weight_in_time",
	"weight_out_time",
	"owner",
	"spb",
	"ticket_number",
	"jumlah_janjang",
	"total_brondolan",
	"bruto",
	"tara",
	"netto",
	"latitude",
	"longitude",
	"satelite_count",
	"gps_acc",
	"creation",
	"wb_type",
	"docstatus",
]

SPB_FIELDS = [
	"name",
	"posting_date",
	"tipe_kendaraan",
	"kendaraan",
	"no_polisi",
	"driver_code",
]


def _combine_datetime(date_value, time_value):
	"""Gabungkan Date + Time jadi Datetime. Time dari DB berupa timedelta."""
	if not date_value or time_value is None:
		return None

	date_value = getdate(date_value)

	if isinstance(time_value, timedelta):
		return datetime.combine(date_value, dtime()) + time_value
	if isinstance(time_value, dtime):
		return datetime.combine(date_value, time_value)

	return get_datetime(f"{date_value} {time_value}")


def _map_by_name(doctype, names, fields):
	"""Ambil sekaligus lalu index by name, supaya tidak query per baris."""
	names = {n for n in names if n}
	if not names:
		return {}

	rows = frappe.get_all(
		doctype,
		filters=[["name", "in", list(names)]],
		fields=fields,
		limit_page_length=0,
	)
	return {row["name"]: row for row in rows}


def _build_filters(estate_code, from_date, to_date, spb_no, wb_type, modified_after):
	filters = []

	if estate_code:
		filters.append(["unit", "=", estate_code])
	if from_date:
		filters.append(["posting_date", ">=", getdate(from_date)])
	if to_date:
		filters.append(["posting_date", "<=", getdate(to_date)])
	if spb_no:
		filters.append(["spb", "=", spb_no])
	if wb_type is not None and wb_type != "":
		filters.append(["wb_type", "=", int(wb_type)])
	if modified_after:
		filters.append(["modified", ">", get_datetime(modified_after)])

	return filters


@frappe.whitelist()
def get_timbangan(trans_no):
	"""Kembalikan satu data Timbangan berdasarkan trans_no, atau None kalau tidak ada."""
	if not trans_no:
		frappe.throw(_("Parameter trans_no wajib diisi."))

	timbangan_rows = frappe.get_all(
		"Timbangan",
		filters=[["trans_no", "=", trans_no]],
		fields=TIMBANGAN_FIELDS,
		order_by="creation asc",
		limit_page_length=1,
	)

	data = _build_data(timbangan_rows)

	return data[0] if data else None


@frappe.whitelist()
def get_all_timbangan(
	estate_code=None,
	from_date=None,
	to_date=None,
	spb_no=None,
	wb_type=None,
	modified_after=None,
	limit=None,
	offset=0,
):
	"""Kembalikan daftar data Timbangan beserta data turunannya.

	Filter opsional:
		estate_code    : Unit
		from_date      : posting_date >= from_date
		to_date        : posting_date <= to_date
		spb_no         : Surat Pengantar Buah
		wb_type        : 0 = baru WB in, 1 = sudah WB out
		modified_after : untuk sinkronisasi inkremental
		limit/offset   : paging, limit kosong berarti semua baris
	"""
	timbangan_rows = frappe.get_all(
		"Timbangan",
		filters=_build_filters(estate_code, from_date, to_date, spb_no, wb_type, modified_after),
		fields=TIMBANGAN_FIELDS,
		order_by="posting_date asc, creation asc",
		limit_page_length=int(limit) if limit else 0,
		limit_start=int(offset or 0),
	)

	return _build_data(timbangan_rows)


def _build_data(timbangan_rows):
	"""Petakan baris Timbangan + data turunannya ke bentuk output API."""
	if not timbangan_rows:
		return []

	spb_map = _map_by_name("Surat Pengantar Buah", [r.get("spb") for r in timbangan_rows], SPB_FIELDS)
	scp_map = _map_by_name(
		"Security Check Point",
		[r.get("ticket_number") for r in timbangan_rows],
		["name", "supplier"],
	)
	supplier_map = _map_by_name(
		"Supplier",
		[s.get("supplier") for s in scp_map.values()],
		["name", "supplier_name"],
	)
	driver_map = _map_by_name(
		"Employee",
		[s.get("driver_code") for s in spb_map.values()],
		["name", "first_name"],
	)
	user_map = _map_by_name(
		"User",
		[r.get("owner") for r in timbangan_rows],
		["name", "full_name"],
	)

	data = []

	for row in timbangan_rows:
		spb = spb_map.get(row.get("spb")) or {}
		scp = scp_map.get(row.get("ticket_number")) or {}
		supplier_code = scp.get("supplier")
		supplier = supplier_map.get(supplier_code) or {}
		driver = driver_map.get(spb.get("driver_code")) or {}
		user = user_map.get(row.get("owner")) or {}

		is_external = 1 if spb.get("tipe_kendaraan") == "Eksternal" else 0

		data.append({
			"estate_code": row.get("unit"),
			"trans_no": row.get("trans_no"),
			"wb_in_at": _combine_datetime(row.get("posting_date"), row.get("weight_in_time")),
			"wb_out_at": _combine_datetime(row.get("posting_date"), row.get("weight_out_time")),
			"wb_in_by": row.get("owner"),
			"wb_out_by": row.get("owner"),
			"is_external": is_external,
			"supplier_code": supplier_code,
			"supplier_name": supplier.get("supplier_name"),
			"spb_no": row.get("spb"),
			"spb_date": spb.get("posting_date"),
			# TODO: sumber data is_contract belum ditentukan
			"is_contract": 0,
			"veh_code": spb.get("kendaraan"),
			"veh_regno": spb.get("no_polisi"),
			"driver_code": spb.get("driver_code"),
			"driver_name": driver.get("first_name"),
			"total_jjg": row.get("jumlah_janjang"),
			"total_brd": row.get("total_brondolan"),
			"bruto": row.get("bruto"),
			"tarra": row.get("tara"),
			"netto": row.get("netto"),
			"trans_type": is_external,
			"latitude": row.get("latitude"),
			"longitude": row.get("longitude"),
			"satelite_count": row.get("satelite_count"),
			"gps_acc": row.get("gps_acc"),
			"created_at": row.get("creation"),
			"created_by": user.get("full_name"),
			"created_by_code": row.get("owner"),
			"wb_type": row.get("wb_type"),
			"is_active": 1 if row.get("docstatus", 0) < 2 else 0,
		})

	return data
