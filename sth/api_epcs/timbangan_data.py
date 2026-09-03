# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

"""API untuk menarik data dari doctype Timbangan."""

from datetime import datetime, time as dtime, timedelta

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, getdate

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
	"receive_type"
]

SPB_FIELDS = [
	"name",
	"posting_date",
	"tipe_kendaraan",
	"kendaraan",
	"no_polisi",
	"driver_code",
	"trans_no",
]


# Nilai Select receive_type di doctype Timbangan. Alias pendeknya disediakan
# supaya pemanggil cukup mengirim "internal" atau "eksternal"; nilai penuhnya
# tetap boleh dipakai apa adanya.
RECEIVE_TYPE_ALIAS = {
	"internal": "TBS Internal",
	"eksternal": "TBS Eksternal",
	"external": "TBS Eksternal",
}


def _normalize_receive_type(receive_type):
	"""Terjemahkan alias jadi nilai Select-nya; yang tidak dikenal diteruskan."""
	if receive_type is None or receive_type == "":
		return None

	return RECEIVE_TYPE_ALIAS.get(str(receive_type).strip().lower(), receive_type)


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


def _build_filters(estate_code, from_date, to_date, spb_no, wb_type, modified_after, date, receive_type=None):
	filters = []

	if estate_code:
		filters.append(["unit", "=", estate_code])
	receive_type = _normalize_receive_type(receive_type)
	if receive_type:
		filters.append(["receive_type", "=", receive_type])
	if from_date:
		filters.append(["posting_date", ">=", getdate(from_date)])
	if to_date:
		filters.append(["posting_date", "<=", getdate(to_date)])
	if date:
		filters.append(["posting_date", "=", getdate(date)])
	if spb_no:
		filters.append(["spb", "=", spb_no])
	if wb_type is not None and wb_type != "":
		filters.append(["wb_type", "=", int(wb_type)])
	if modified_after:
		filters.append(["modified", ">", get_datetime(modified_after)])

	return filters


@frappe.whitelist()
def get_timbangan(trans_no=None, date=None, from_date=None, to_date=None, estate_code=None, receive_type=None):
	"""Kembalikan data Timbangan berdasarkan trans_no, atau berdasarkan tanggal.

	- trans_no diisi   : kembalikan satu data (dict) atau None kalau tidak ada.
	- date diisi       : kembalikan list data pada tanggal tersebut saja.
	- from_date/to_date: kembalikan list data dalam rentang tanggal (boleh salah satu saja).

	Salah satu dari trans_no, date, atau from_date/to_date wajib diisi.

	Penyaring tambahan, boleh dipakai bersama yang mana pun di atas:
		estate_code  : Unit
		receive_type : "internal" / "eksternal" (atau nilai penuhnya, mis.
		               "TBS Internal"), menyaring TBS kebun sendiri dari
		               TBS pihak ketiga.
	"""
	if not trans_no and not date and not from_date and not to_date:
		frappe.throw(_("Parameter trans_no, date, atau from_date/to_date wajib diisi."))

	if trans_no:
		filters = [["trans_no", "=", trans_no]]
	elif date:
		filters = [["posting_date", "=", getdate(date)]]
	else:
		filters = []
		if from_date:
			filters.append(["posting_date", ">=", getdate(from_date)])
		if to_date:
			filters.append(["posting_date", "<=", getdate(to_date)])

	if estate_code:
		filters.append(["unit", "=", estate_code])
	receive_type = _normalize_receive_type(receive_type)
	if receive_type:
		filters.append(["receive_type", "=", receive_type])

	timbangan_rows = frappe.get_all(
		"Timbangan",
		filters=filters,
		fields=TIMBANGAN_FIELDS,
		order_by="posting_date asc, creation asc",
		limit_page_length=1 if trans_no else 0,
	)

	data = _build_data(timbangan_rows)

	if trans_no:
		return data[0] if data else None

	return data


@frappe.whitelist()
def get_all_timbangan(
	estate_code=None,
	from_date=None,
	to_date=None,
	spb_no=None,
	wb_type=None,
	modified_after=None,
	limit=None,
	date=None,
	offset=0,
	receive_type=None,
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
		receive_type   : "internal" / "eksternal" (atau nilai penuhnya, mis.
		                 "TBS Internal")
	"""
	timbangan_rows = frappe.get_all(
		"Timbangan",
		filters=_build_filters(
			estate_code, from_date, to_date, spb_no, wb_type, modified_after, date, receive_type
		),
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
		["name", "supplier", "trans_no"],
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

		trans_type = 0
		if row.get("receive_type") == "TBS Eksternal":
			trans_type = 2

		data.append({
			"estate_code": row.get("unit"),
			"trans_no": row.get("name"),
			"wb_in_at": _combine_datetime(row.get("posting_date"), row.get("weight_in_time")),
			"wb_out_at": _combine_datetime(row.get("posting_date"), row.get("weight_out_time")),
			"wb_in_by": row.get("owner"),
			"wb_out_by": row.get("owner"),
			"is_external": is_external,
			"supplier_code": supplier_code,
			"supplier_name": supplier.get("supplier_name"),
			# Dua pasang nomor dokumen: yang dari Security Check Point lewat
			# ticket_number, dan yang dari Surat Pengantar Buah lewat link spb di
			# Timbangan. spb_no adalah nomor SPB milik sistem luar (trans_no);
			# nama dokumen SPB di ERP dikirim terpisah sebagai erp_spb_no.
			"verifikasi_security": row.get("ticket_number"),
			"verifikasi_security_trans_no": scp.get("trans_no"),
			"erp_spb_no": row.get("spb"),
			"spb_no": spb.get("trans_no"),
			"spb_date": spb.get("posting_date"),
			# TODO: sumber data is_contract belum ditentukan
			"is_contract": 0,
			"veh_code": spb.get("kendaraan"),
			"veh_regno": spb.get("no_polisi"),
			"driver_code": spb.get("driver_code"),
			"driver_name": driver.get("first_name"),
			# Keduanya Float di doctype Timbangan, tapi EPCS menunggunya bulat.
			# cint memotong pecahannya, bukan membulatkan; jumlah_janjang memang
			# sudah berpresisi 0, jadi yang bisa kehilangan pecahan cuma
			# total_brondolan.
			"total_jjg": cint(row.get("jumlah_janjang")),
			"total_brd": cint(row.get("total_brondolan")),
			"bruto": row.get("bruto"),
			"tarra": row.get("tara"),
			"netto": row.get("netto"),
			"trans_type": trans_type,
			"latitude": row.get("latitude"),
			"longitude": row.get("longitude"),
			"satelite_count": row.get("satelite_count"),
			"gps_acc": row.get("gps_acc"),
			"created_at": row.get("creation"),
			"created_by": user.get("full_name"),
			"created_by_code": row.get("owner"),
			"wb_type": 0 if row.get("docstatus", 0) < 1 else 1,
			"is_active": 1 if row.get("docstatus", 0) < 2 else 0,
		})

	return data
