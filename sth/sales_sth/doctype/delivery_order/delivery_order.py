# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from erpnext.stock.doctype.delivery_note.delivery_note import DeliveryNote
from frappe.model.mapper import get_mapped_doc
from frappe.utils import add_to_date, cint, flt, format_datetime, get_datetime, now_datetime, nowdate, nowtime
from sth.sales_sth.custom.sales_order import update_per_delivery_ordered_on_submit_cancel
from sth.utils.qr_generator import get_qr_svg
import json

# QR transporter hanya berlaku sehari kerja: sopir yang dapat QR pagi ini tidak
# bisa memakainya lagi besok tanpa diterbitkan ulang oleh petugas DO.
QR_BERLAKU_JAM = 12

# Keterangan barang di dalam QR sengaja dibatasi: QR yang terlalu padat jadi
# susah dibaca kamera di pos, sementara isinya cuma keterangan.
BARANG_QR_MAKS_BARIS = 3
BARANG_QR_PANJANG_NAMA = 30


class DeliveryOrder(DeliveryNote):
	def validate(self):
		super().validate()
		self.terbitkan_qr_transporter()

	def terbitkan_qr_transporter(self):
		"""Terbitkan QR untuk baris transporter yang belum punya atau sudah kedaluwarsa.

		QR yang masih berlaku sengaja tidak diganti: kertasnya sudah dibawa sopir,
		dan menyimpan ulang DO tidak boleh membatalkan QR yang sedang dipakai.
		"""
		keterangan = ringkas_barang_do(self.get("items"))
		for row in self.get("delivery_order_transporter") or []:
			if not qr_masih_berlaku(row):
				terbitkan_qr_baris(row, keterangan)

	def on_submit(self):
		update_per_delivery_ordered_on_submit_cancel(self, "on_submit")

	def on_cancel(self):
		update_per_delivery_ordered_on_submit_cancel(self, "on_cancel")


@frappe.whitelist()
def make_delivery_note(source_name, target_doc=None, transporter_data=None):

	if isinstance(transporter_data, str):
		transporter_data = json.loads(transporter_data) if transporter_data != 'null' else None
	
	def set_missing_values(source, target):
		"""Set nilai-nilai yang diperlukan untuk Delivery Note"""
		target.posting_date = nowdate()
		target.posting_time = nowtime()
		
		# Set transporter info jika ada
		if transporter_data:
			target.transporter = transporter_data.get('transporter')
			target.transporter_name = transporter_data.get('transporter_name')
			target.lr_date = transporter_data.get('transport_receipt_date')
			target.vehicle_no = transporter_data.get('vehicle_no')
			target.driver_name = transporter_data.get('driver_name')
			target.driver = transporter_data.get('driver')  # Untuk field driver jika ada
			
			# Custom fields lainnya jika ada
			if transporter_data.get('driver_contact'):
				target.driver_contact = transporter_data.get('driver_contact')
		
		# Set reference ke Delivery Order
		target.delivery_order = source.name
		
		# Run method bawaan jika ada
		if hasattr(target, 'set_missing_values'):
			target.run_method("set_missing_values")
		
		if hasattr(target, 'calculate_taxes_and_totals'):
			target.run_method("calculate_taxes_and_totals")
	
	def update_item(source, target, source_parent):
		"""Update item dari Delivery Order ke Delivery Note"""
		target.qty = source.qty
		target.stock_qty = source.qty
		
		# Set warehouse
		if source.warehouse:
			target.warehouse = source.warehouse
		elif source_parent.set_warehouse:
			target.warehouse = source_parent.set_warehouse
		
		# Set reference ke Delivery Order
		target.delivery_order = source_parent.name
		target.delivery_order_item = source.name
		
		# Set reference ke Sales Order jika ada
		if source.against_sales_order:
			target.against_sales_order = source.against_sales_order
			target.so_detail = source.so_detail
	
	# Mapping configuration
	doclist = get_mapped_doc(
		"Delivery Order",
		source_name,
		{
			"Delivery Order": {
				"doctype": "Delivery Note",
				"field_map": {
					"name": "delivery_order",
					"posting_date": "posting_date",
					"posting_time": "posting_time"
				},
				"validation": {
					"docstatus": ["=", 1]
				}
			},
			"Delivery Order Item": {
				"doctype": "Delivery Note Item",
				"field_map": {
					"name": "delivery_order_item",
					"parent": "delivery_order",
					"against_sales_order": "against_sales_order",
					"so_detail": "so_detail"
				},
				"postprocess": update_item
			}
		},
		target_doc,
		set_missing_values
	)
	
	return doclist


@frappe.whitelist()
def get_transporter_list(delivery_order):
	"""
	Mendapatkan list transporter dari Delivery Order
	untuk ditampilkan di dialog
	"""
	transporters = frappe.get_all(
		"Delivery Order Transporter",
		filters={"parent": delivery_order},
		fields=[
			"name",
			"transporter",
			"transporter_name", 
			"vehicle_no",
			"driver_name",
			"driver_contact",
			"lr_no",
			"lr_date"
		]
	)
	
	return transporters

def qr_masih_berlaku(row):
	"""Baris punya QR yang belum lewat masa berlakunya."""
	if not row.get("qr_token") or not row.get("qr_berlaku_sampai"):
		return False

	return get_datetime(row.get("qr_berlaku_sampai")) > now_datetime()


def ringkas_barang_do(items):
	"""Ringkasan barang DO untuk ditulis di QR sebagai keterangan.

	Cuma keterangan: yang menentukan barang di Security Check Point tetap baris
	item DO-nya sendiri, bukan tulisan ini. Karena itu isinya boleh dipangkas -
	dan memang dipangkas, karena tiap huruf tambahan membuat QR makin rapat dan
	makin susah dibaca kamera murah di pos yang remang.
	"""
	ringkas = []
	for item in items or []:
		nama = (item.get("item_name") or item.get("item_code") or "").strip()
		if not nama:
			continue

		nama = nama[:BARANG_QR_PANJANG_NAMA]
		qty = flt(item.get("qty"))
		uom = item.get("uom") or item.get("stock_uom") or ""
		ringkas.append(" ".join(bagian for bagian in [nama, f"{qty:g}", uom] if bagian))

		if len(ringkas) >= BARANG_QR_MAKS_BARIS:
			break

	return ringkas


def terbitkan_qr_baris(row, keterangan_barang=None):
	"""Bikin token baru untuk satu baris transporter beserta gambar QR-nya.

	Yang mengikat cuma nama DO dan token acak; barangnya ikut ditulis sekadar
	keterangan supaya QR yang discan pakai aplikasi biasa masih memberi tahu
	muatannya. Masa berlakunya tetap tidak ikut ditulis di sana supaya tidak ada
	yang bisa memperpanjang sendiri dengan mencetak QR buatan tangan - pos satpam
	selalu membacanya dari baris ini.
	"""
	dibuat = now_datetime()

	isi = {"delivery_order": row.parent, "token": frappe.generate_hash(length=24)}
	if keterangan_barang:
		isi["barang"] = keterangan_barang

	row.qr_token = isi["token"]
	row.qr_dibuat_pada = dibuat
	row.qr_berlaku_sampai = add_to_date(dibuat, hours=QR_BERLAKU_JAM)
	# Koreksi kesalahan diturunkan ke "M" supaya keterangan barang tidak menambah
	# jumlah kotak QR: dengan "H" bawaan, QR dua barang jadi 69x69 kotak dan di
	# cetakan 190px tiap kotak tinggal 2,7px - terlalu rapat untuk kamera pos.
	row.qr_code = get_qr_svg(json.dumps(isi), error="M")


@frappe.whitelist()
def buat_ulang_qr_transporter(delivery_order, semua=0):
	"""Terbitkan ulang QR transporter dari tombol di form Delivery Order.

	Ditulis lewat db_set supaya tetap jalan sesudah DO disubmit - justru di situ
	kebutuhannya, karena QR kedaluwarsa biasanya baru ketahuan waktu sopir sudah
	di pos. Tanpa `semua`, baris yang QR-nya masih berlaku dilewati agar QR yang
	sudah dipegang sopir lain tidak ikut mati.
	"""
	doc = frappe.get_doc("Delivery Order", delivery_order)
	doc.check_permission("write")

	keterangan = ringkas_barang_do(doc.get("items"))
	diperbarui = 0
	for row in doc.get("delivery_order_transporter") or []:
		if not cint(semua) and qr_masih_berlaku(row):
			continue

		terbitkan_qr_baris(row, keterangan)
		frappe.db.set_value(
			"Delivery Order Transporter",
			row.name,
			{
				"qr_token": row.qr_token,
				"qr_dibuat_pada": row.qr_dibuat_pada,
				"qr_berlaku_sampai": row.qr_berlaku_sampai,
				"qr_code": row.qr_code,
			},
			update_modified=False,
		)
		diperbarui += 1

	return {"diperbarui": diperbarui, "total": len(doc.get("delivery_order_transporter") or [])}


@frappe.whitelist()
def resolve_qr_transporter(qr_text):
	"""Terjemahkan hasil scan QR transporter jadi data Dispatch untuk pos satpam.

	Semuanya dibaca ulang dari baris transporter, bukan dari isi QR: nama DO di
	dalam QR cuma dipakai untuk pesan kesalahan kalau tokennya sudah tidak ada.
	"""
	token = ambil_token_qr(qr_text)
	if not token:
		frappe.throw(_("QR tidak dikenali. Pastikan yang discan adalah QR transporter dari Delivery Order."))

	baris = frappe.db.get_value(
		"Delivery Order Transporter",
		{"qr_token": token},
		[
			"name",
			"parent",
			"driver",
			"driver_name",
			"vehicle_no",
			"transporter",
			"transporter_name",
			"qr_berlaku_sampai",
		],
		as_dict=True,
	)

	if not baris:
		frappe.throw(
			_("QR ini sudah tidak berlaku - kemungkinan sudah diterbitkan ulang. Minta QR terbaru dari petugas Delivery Order.")
		)

	if get_datetime(baris.qr_berlaku_sampai) <= now_datetime():
		frappe.throw(
			_("QR sudah kedaluwarsa sejak {0}. Minta petugas menerbitkan ulang QR di Delivery Order {1}.").format(
				format_datetime(baris.qr_berlaku_sampai), baris.parent
			)
		)

	docstatus = frappe.db.get_value("Delivery Order", baris.parent, "docstatus")
	if docstatus != 1:
		frappe.throw(
			_("Delivery Order {0} belum disubmit atau sudah dibatalkan, kendaraan tidak bisa dilepas.").format(baris.parent)
		)

	return {
		"delivery_order": baris.parent,
		"transporter_row": baris.name,
		"driver": baris.driver,
		"driver_name": baris.driver_name,
		"vehicle_no": baris.vehicle_no,
		"transporter": baris.transporter,
		"transporter_name": baris.transporter_name,
		"qr_berlaku_sampai": baris.qr_berlaku_sampai,
		# Keterangan saja, dan dibaca ulang dari DO - bukan dari tulisan di QR,
		# yang bisa saja dicetak sebelum baris itemnya terakhir diubah.
		"barang": frappe.get_all(
			"Delivery Order Item",
			filters={"parent": baris.parent},
			fields=["item_code", "item_name", "qty", "uom"],
			order_by="idx",
		),
	}


def ambil_token_qr(qr_text):
	"""Ambil token dari teks QR; menerima JSON maupun tokennya langsung."""
	qr_text = (qr_text or "").strip()
	if not qr_text:
		return None

	try:
		isi = json.loads(qr_text)
	except ValueError:
		# Scanner keyboard kadang cuma meneruskan tokennya saja.
		return qr_text

	if isinstance(isi, dict):
		return isi.get("token")

	return None
