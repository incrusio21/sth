import csv
import json
import os

import frappe
from frappe.utils import cint

from sth.custom.api import USER_API

DOCTYPE = "Buku Kerja Mandor Panen"


def execute(path, terapkan=0, trans_no=None):
	"""Kirim ulang request_payload BKM Panen yang gagal sync dari log sistem luar.

	path menunjuk ke CSV ekspor log_erp_next_request (dipisah tab, kolom
	request_payload dan started_at). Tiap payload dimasukkan persis seperti
	POST /api/resource/Buku Kerja Mandor Panen: sebagai USER_API, lewat insert()
	yang sama, jadi kiriman dengan trans_no yang sudah ada digabung dan baris yang
	sudah tercatat dibalas dengan dokumennya -- aman diulang.

	Diputar satu per satu menurut started_at, bukan bersamaan. Sebagian besar
	TimestampMismatchError di log asalnya justru dari beberapa request yang
	menyimpan baris premi mandor yang sama pada saat yang sama.

	Default-nya uji coba: tiap payload dicoba lalu di-rollback. Karena itu kiriman
	yang seharusnya digabung ke dokumen dari payload sebelumnya akan tampil sebagai
	dokumen baru di uji coba. Tulis sungguhan dengan terapkan=1. trans_no membatasi
	ke satu trans_no, untuk dicoba satu per satu dulu.

	Hasilnya ditulis ke <path>.hasil.csv: payload, nama dokumen atau pesan error.
	"""
	terapkan = cint(terapkan)
	daftar = baca_payload(path, trans_no)

	pengguna_asal = frappe.session.user
	frappe.set_user(USER_API)

	hasil = []
	try:
		for started_at, payload in daftar:
			frappe.db.savepoint("kirim_ulang_bkm_panen")
			try:
				doc = frappe.new_doc(DOCTYPE, **json.loads(payload)).insert()
				status, keterangan = "berhasil", doc.name
			except Exception as e:
				frappe.db.rollback(save_point="kirim_ulang_bkm_panen")
				status, keterangan = "gagal", f"{type(e).__name__}: {frappe.utils.strip_html(str(e))}"
			else:
				if terapkan:
					frappe.db.commit()
				else:
					frappe.db.rollback(save_point="kirim_ulang_bkm_panen")
			finally:
				frappe.clear_messages()

			hasil.append((started_at, json.loads(payload).get("trans_no"), status, keterangan, payload))
			print(f"{status:8} {hasil[-1][1]} {keterangan}")
	finally:
		frappe.set_user(pengguna_asal)

	tulis_hasil(path, hasil)

	berhasil = sum(1 for h in hasil if h[2] == "berhasil")
	print(f"\n{berhasil} berhasil, {len(hasil) - berhasil} gagal dari {len(hasil)} payload.")
	if not terapkan:
		print("Uji coba, tidak ada yang tersimpan. Tulis dengan --kwargs \"{'path': ..., 'terapkan': 1}\".")


def baca_payload(path, trans_no=None):
	"""Payload unik urut started_at. Payload yang sama persis cukup dikirim sekali."""
	with open(path, encoding="utf-8-sig", newline="") as f:
		baris = list(csv.DictReader(f, delimiter="\t"))

	sudah = set()
	daftar = []
	for b in sorted(baris, key=lambda b: b["started_at"]):
		payload = b["request_payload"]
		if payload in sudah:
			continue
		if trans_no and json.loads(payload).get("trans_no") != trans_no:
			continue

		sudah.add(payload)
		daftar.append((b["started_at"], payload))

	return daftar


def tulis_hasil(path, hasil):
	tujuan = os.path.splitext(path)[0] + ".hasil.csv"
	with open(tujuan, "w", encoding="utf-8", newline="") as f:
		w = csv.writer(f)
		w.writerow(["started_at", "trans_no", "status", "keterangan", "request_payload"])
		w.writerows(hasil)

	print(f"Hasil ditulis ke {tujuan}")
