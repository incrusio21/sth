# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import json
from urllib.parse import unquote

import frappe
from frappe.model.document import Document
from frappe.query_builder import Interval
from frappe.query_builder.functions import Now

from sth.custom.api import USER_API

# Cuma request yang mengubah data. GET dari sistem luar sering dan tidak pernah
# jadi masalah, mencatatnya hanya membesarkan tabel.
METHOD_DICATAT = ("POST", "PUT", "PATCH", "DELETE")

# Batas payload yang disimpan. Payload BKM biasa cuma beberapa KB; yang lebih
# besar dari ini dipotong, cukup untuk dilihat tapi tidak sampai membengkakkan
# satu baris.
BATAS_PAYLOAD = 64 * 1024
BATAS_ERROR = 1000


class LogAPIMasuk(Document):
	@staticmethod
	def clear_old_logs(days=30):
		# dipanggil Log Settings tiap hari, harinya diatur dari sana
		table = frappe.qb.DocType("Log API Masuk")
		frappe.db.delete(table, filters=(table.creation < (Now() - Interval(days=days))))


def catat_request_api(request, response):
	"""Hook after_request: catat tiap request tulis dari sistem luar.

	Supaya tabelnya tetap kecil, request yang berhasil cuma dicatat ringkas
	(endpoint, status, trans_no, dokumen yang terbentuk) tanpa payload. Payload
	dan pesan error -- tanpa traceback -- hanya disimpan kalau gagal, karena
	cuma di situ payload-nya dibutuhkan untuk dikirim ulang. Baris lama dibuang
	Log Settings, lihat default_log_clearing_doctypes di hooks.

	Hook ini jalan sesudah transaksi request di-commit atau di-rollback, jadi
	barisnya di-commit sendiri. Kegagalan di sini tidak boleh mengubah respons
	yang sudah jadi, karena itu semua error cuma masuk ke logger.
	"""
	try:
		if (
			frappe.session.user != USER_API
			or request.method not in METHOD_DICATAT
			or not request.path.startswith("/api/")
		):
			return

		http_status = response.status_code if response is not None else 500
		berhasil = http_status < 400
		payload = request.get_data(as_text=True) or ""
		body = baca_body(response)

		data = body.get("data") if isinstance(body.get("data"), dict) else {}
		reference_doctype = data.get("doctype") or doctype_dari_path(request.path)

		log = frappe.new_doc("Log API Masuk")
		log.update({
			"status": "Berhasil" if berhasil else "Gagal",
			"method": request.method,
			"http_status": http_status,
			"endpoint": request.path[:255],
			"reference_doctype": reference_doctype
			if reference_doctype and frappe.db.exists("DocType", reference_doctype)
			else None,
			"reference_name": data.get("name"),
			"trans_no": ambil_trans_no(payload, data),
		})

		if not berhasil:
			log.error = pesan_error(body, response)
			log.request_payload = payload[:BATAS_PAYLOAD]

		log.db_insert()
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.logger("log_api_masuk").error("Gagal mencatat request API", exc_info=True)


def baca_body(response):
	if response is None or response.mimetype != "application/json":
		return {}

	try:
		body = json.loads(response.get_data(as_text=True))
	except ValueError:
		return {}

	return body if isinstance(body, dict) else {}


def doctype_dari_path(path):
	# /api/resource/<doctype>/... dan /api/v2/document/<doctype>/...
	bagian = [unquote(b) for b in path.split("/") if b]
	for awalan in ("resource", "document"):
		if awalan in bagian and bagian.index(awalan) + 1 < len(bagian):
			return bagian[bagian.index(awalan) + 1]


def ambil_trans_no(payload, data):
	if data.get("trans_no"):
		return data["trans_no"]

	try:
		kiriman = json.loads(payload)
	except ValueError:
		return None

	return kiriman.get("trans_no") if isinstance(kiriman, dict) else None


def pesan_error(body, response):
	pesan = body.get("exception") or body.get("exc_type")
	if not pesan and body.get("_server_messages"):
		pesan = body["_server_messages"]
	if not pesan and response is not None:
		pesan = response.get_data(as_text=True)

	return frappe.utils.strip_html(str(pesan or ""))[:BATAS_ERROR]
