# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

"""API untuk menarik data dari doctype Timbangan."""

import re
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
	"receive_type",
	"no_polisi",
	"driver_name",
]

SPB_FIELDS = [
	"name",
	"unit",
	"posting_date",
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


def _normalize_key(value):
	"""Samakan bentuk nomor polisi / nama sebelum dicocokkan.

	Huruf besar, tanpa spasi dan tanda baca — "BH 8043 MH" dan "bh8043mh" jadi satu
	kunci, begitu juga "M. MUSTAMIR" dan "M MUSTAMIR".
	"""
	return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def _map_unik(rows, key_field, value_field):
	"""Index baris berdasarkan satu kolom, buang kunci yang dipakai lebih dari satu.

	Pencocokan lewat teks selalu bisa kembar. Yang kembar sengaja dijatuhkan jadi
	kosong: lebih baik kodenya tidak dikirim daripada menunjuk baris yang salah.
	"""
	hasil = {}

	for row in rows:
		key = _normalize_key(row.get(key_field))
		if not key:
			continue
		hasil[key] = None if key in hasil else row.get(value_field)

	return {key: value for key, value in hasil.items() if value}


def _map_vra_by_plate():
	"""Index Alat Berat Dan Kendaraan berdasarkan nomor polisinya.

	SPB.kendaraan menunjuk doctype ini, tapi hampir tidak pernah diisi (5 dari 390
	baris internal), sementara nomor polisinya ada di hampir semua baris. Plat yang
	dipakai lebih dari satu kendaraan dibuang: lebih baik veh_code kosong daripada
	menunjuk kendaraan yang salah.
	"""
	return _map_unik(
		frappe.get_all(
			"Alat Berat Dan Kendaraan",
			filters=[["no_pol", "!=", ""]],
			fields=["name", "no_pol"],
			limit_page_length=0,
		),
		"no_pol",
		"name",
	)


def _map_employee_by_name():
	"""Index Employee berdasarkan nama lengkapnya.

	Security Check Point menyimpan nama sopir sebagai teks, bukan link, jadi
	kodenya cuma bisa dicari lewat nama. Nama kembar — 34 nama dipakai lebih dari
	satu Employee — dibuang oleh _map_unik.
	"""
	return _map_unik(
		frappe.get_all(
			"Employee",
			filters=[["employee_name", "!=", ""]],
			fields=["name", "employee_name"],
			limit_page_length=0,
		),
		"employee_name",
		"name",
	)


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
		["name", "supplier", "trans_no", "qr_code_scan", "total_jjg", "total_brd"],
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
	vra_by_plate = _map_vra_by_plate()
	employee_by_name = _map_employee_by_name()

	data = []

	for row in timbangan_rows:
		spb = spb_map.get(row.get("spb")) or {}
		scp = scp_map.get(row.get("ticket_number")) or {}
		supplier_code = scp.get("supplier")
		supplier = supplier_map.get(supplier_code) or {}
		driver = driver_map.get(spb.get("driver_code")) or {}
		user = user_map.get(row.get("owner")) or {}

		# Keduanya turun dari receive_type. is_external dulu dibaca dari
		# spb.tipe_kendaraan, yang tidak pernah bernilai "Eksternal": TBS
		# Eksternal justru tidak punya SPB sama sekali, jadi nilainya selalu 0
		# dan berlawanan dengan trans_type di baris yang sama.
		no_polisi = row.get("no_polisi") or spb.get("no_polisi")

		eksternal = row.get("receive_type") == "TBS Eksternal"
		is_external = 1 if eksternal else 0
		trans_type = 2 if eksternal else 0

		driver_name = row.get("driver_name") or driver.get("first_name")

		# Sopirnya tidak pernah jadi satu master. Yang internal karyawan sendiri,
		# jadi dicari di Employee lewat namanya; yang eksternal sopir pihak ketiga
		# yang QR-nya di-scan security, jadi yang dikirim ID Driver-nya. Dua jenis
		# ID dalam satu field memang, tapi is_external membedakan barisnya.
		driver_code = spb.get("driver_code")
		if not driver_code:
			if eksternal:
				driver_code = scp.get("qr_code_scan")
			else:
				driver_code = employee_by_name.get(_normalize_key(driver_name))

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
			# Link kendaraan di SPB dipakai kalau ada; kalau tidak, kendaraannya
			# dicari dari nomor polisi. Kendaraan pihak ketiga memang tidak
			# terdaftar, jadi baris TBS Eksternal tetap kosong.
			"veh_code": spb.get("kendaraan") or vra_by_plate.get(_normalize_key(no_polisi)),
			# Nomor polisi dan nama sopir dibaca dari Timbangan-nya sendiri dulu,
			# baru jatuh ke SPB. Keduanya di-fetch dari Security Check Point
			# (license_plate & driver_name, asalnya dari Driver yang di-scan),
			# jadi TBS Eksternal — yang tidak pernah punya SPB — tetap terisi.
			# Untuk TBS Internal keduanya tidak pernah berbeda isi dari SPB.
			"veh_regno": no_polisi,
			"driver_code": driver_code,
			"driver_name": driver_name,
			# Keduanya Float di doctype Timbangan, tapi EPCS menunggunya bulat.
			# cint memotong pecahannya, bukan membulatkan; jumlah_janjang memang
			# sudah berpresisi 0, jadi yang bisa kehilangan pecahan cuma
			# total_brondolan.
			"total_jjg": cint(row.get("jumlah_janjang")),
			"total_brd": cint(row.get("total_brondolan")),
			# Angka yang dicatat pos sendiri, sebagai pembanding hitungan
			# rincian SPB di atas. Dibulatkan ke bawah dengan alasan yang sama.
			"total_jjg_scp": cint(scp.get("total_jjg")),
			"total_brd_scp": cint(scp.get("total_brd")),
			# Kebun yang memanen, dari SPB — estate_code di atas pabrik yang
			# menimbang. Unit SPB sudah memuat koreksi kebun dari pos (lihat
			# koreksi_pos di Security Check Point). TBS Eksternal tidak punya SPB,
			# jadi kosong.
			"estate_spb": spb.get("unit"),
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
