import contextlib

import frappe
from frappe.utils import cint, flt

SEHARI = 24 * 3600


def hitung_jam_desimal(jam_mulai, jam_selesai):
	"""Selisih dua jam dalam satuan jam desimal.

	Shift yang melewati tengah malam (mis. 23:00 → 01:00) ditambah 24 jam supaya
	tidak jadi negatif. Kalau salah satu jam kosong, hasilnya 0 — bukan None —
	supaya aman dijumlahkan di SQL maupun Python.
	"""
	if not jam_mulai or not jam_selesai:
		return 0.0

	mulai = _ke_detik(jam_mulai)
	selesai = _ke_detik(jam_selesai)

	if mulai is None or selesai is None:
		return 0.0

	selisih = selesai - mulai
	if selisih < 0:
		selisih += SEHARI

	return round(selisih / 3600.0, 2)


def _ke_detik(nilai):
	"""Ubah nilai field Time jadi detik sejak tengah malam.

	Frappe mengembalikan Time sebagai timedelta, tapi lewat API atau import bisa
	datang sebagai string "HH:MM:SS" atau "HH:MM".
	"""
	if hasattr(nilai, "total_seconds"):
		return int(nilai.total_seconds())

	if hasattr(nilai, "hour"):
		return nilai.hour * 3600 + nilai.minute * 60 + getattr(nilai, "second", 0)

	bagian = str(nilai).strip().split(":")
	if not bagian or not bagian[0]:
		return None

	try:
		jam = int(bagian[0])
		menit = int(bagian[1]) if len(bagian) > 1 else 0
		detik = int(float(bagian[2])) if len(bagian) > 2 else 0
	except (TypeError, ValueError):
		frappe.log_error(
			"Jam tidak bisa dibaca: {0}".format(nilai), "hitung_jam_desimal"
		)
		return None

	return jam * 3600 + menit * 60 + detik


def set_total_jam_desimal(self, method=None):
	"""Isi total_jam_desimal dari jam_mulai/jam_selesai.

	Dipasang di server (bukan cuma di form) supaya dokumen yang masuk lewat API
	atau import ikut terisi — angka ini yang jadi basis alokasi HM Costing Mill.
	"""
	self.total_jam_desimal = hitung_jam_desimal(
		self.get("jam_mulai"), self.get("jam_selesai")
	)


@contextlib.contextmanager
def izinkan_stock_minus():
	"""Matikan sementara larangan stok minus, lalu kembalikan setelah selesai.

	Membatalkan penerimaan lama membuat stok di tanggal itu berkurang, padahal
	Delivery Note sesudahnya sudah terlanjur mengambil barangnya. Selama
	penggantinya belum dibuat, ERPNext melihat stok minus di masa depan dan
	menolak pembatalannya. Jendela minus itu tidak bisa dihindari dengan
	mengerjakan dokumennya satu per satu, karena yang divalidasi adalah keadaan
	sesudah tanggal itu, bukan urutan pengerjaannya.
	"""
	asal = cint(frappe.db.get_single_value("Stock Settings", "allow_negative_stock"))

	if not asal:
		set_allow_negative_stock(1)

	try:
		yield
	finally:
		# Pekerjaan dokumen yang gagal dibuang dulu, supaya yang ikut ter-commit
		# bersama pengembalian setelan cuma dokumen yang sudah tuntas. Di jalur
		# sukses ini tidak ada efeknya, semuanya sudah di-commit per dokumen.
		frappe.db.rollback()

		if not asal:
			set_allow_negative_stock(0)
			# Harus di-commit di sini juga: kalau pemanggilnya gagal, migrate
			# akan rollback, dan tanpa commit ini site tertinggal dengan stok
			# minus masih diizinkan.
			frappe.db.commit()


def set_allow_negative_stock(nilai):
	frappe.db.set_single_value("Stock Settings", "allow_negative_stock", nilai)
	frappe.clear_document_cache("Stock Settings", "Stock Settings")

	# get_single_value menyimpan hasilnya sepanjang request, dan itulah yang
	# dibaca is_negative_stock_allowed tiap kali SLE dibuat.
	value_cache = getattr(frappe.db, "value_cache", None)
	if value_cache:
		value_cache.pop("Stock Settings", None)


def buat_ulang_ste_sounding(doc, produksi):
	"""Buang Stock Entry dokumen sounding ini, lalu buat ulang lewat create_ste.

	Qty maupun tanggal Stock Entry tidak bisa diubah setelah submit, jadi satu-
	satunya cara membetulkannya adalah membatalkan yang lama, menghapusnya, dan
	membiarkan controller-nya membuat yang baru. Mengembalikan jumlah STE yang
	dibuat, supaya pemanggilnya bisa melaporkannya.
	"""
	for row in frappe.get_all("Stock Entry", filters={"references": doc.name}, fields=["name", "docstatus"]):
		ste = frappe.get_doc("Stock Entry", row.name)
		if ste.docstatus == 1:
			ste.cancel()
		ste.delete()

	if not flt(produksi):
		return 0

	doc.create_ste()
	return 1
