# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from erpnext.stock.doctype.delivery_note.delivery_note import DeliveryNote
from frappe.model.mapper import get_mapped_doc
from frappe.utils import add_to_date, cint, flt, format_datetime, get_datetime, now_datetime, nowdate, nowtime
from sth.mill.doctype.timbangan.timbangan import perbarui_sisa_do_timbangan
from sth.sales_sth.custom.sales_order import make_delivery_order, update_per_delivery_ordered_on_submit_cancel
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
	def autoname(self):
		"""DO pecahan dinamai nomor DO asalnya ditambah huruf (051 -> 051A, 051B).

		Sama dengan kebiasaan di program lama, supaya pembeli dan pos tetap bisa
		mengenali bahwa DO-nya masih bagian dari DO yang sama. DO biasa dibiarkan
		tanpa nama di sini sehingga frappe lanjut memakai naming series.
		"""
		if self.pecahan_dari:
			self.name = nama_do_pecahan(self.pecahan_dari)

	def validate(self):
		super().validate()
		self.validasi_pecahan_dari()
		self.terbitkan_qr_transporter()

	def validasi_pecahan_dari(self):
		if not self.pecahan_dari or self.docstatus != 0:
			return

		if self.pecahan_dari == self.name:
			frappe.throw(_("Pecahan dari DO tidak boleh DO ini sendiri."))

		induk = frappe.db.get_value(
			"Delivery Order", self.pecahan_dari, ["docstatus", "sales_order"], as_dict=True
		)
		if not induk or induk.docstatus != 1:
			frappe.throw(_("Pecahan dari DO {0} harus DO yang sudah disubmit.").format(self.pecahan_dari))

		if self.sales_order and induk.sales_order and self.sales_order != induk.sales_order:
			frappe.throw(
				_("DO {0} milik kontrak {1}, sedangkan DO ini dari kontrak {2}. Pecahan harus dari kontrak yang sama.").format(
					self.pecahan_dari, induk.sales_order, self.sales_order
				)
			)

	def before_update_after_submit(self):
		"""Baris transporter yang ditambah sesudah submit tetap dapat QR.

		Tabel transporternya allow_on_submit, jadi barisnya boleh ditambah dan diubah
		sesudah DO disubmit - dan di situ justru kebutuhannya, karena kendaraannya
		sering baru ditunjuk sesudah DO terbit. Tapi `validate` tidak pernah jalan
		lagi di jalur update-after-submit, jadi baris barunya tersimpan tanpa QR dan
		sopirnya ditolak di pos. Penerbitannya dipanggil ulang di sini, dengan aturan
		yang sama: QR yang masih berlaku tidak diganti.
		"""
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


# Field header yang dibawa DO pecahan dari DO asalnya. Transporter dan ongkos
# angkut sengaja tidak ikut: DO dipecah justru karena transporternya diganti, dan
# ongkos_angkut dipakai sebagai tarif tagihan transportir.
FIELD_IKUT_INDUK = (
	"unit",
	"cost_center",
	"project",
	"set_warehouse",
	"komoditi",
	"tempat_penyerahan",
	"jenis_berikat",
	"force_majeure",
	"perselisihan",
	"lainnya",
	"penandatangan",
	"jabatan_penandatangan",
	"mulai_tanggal_pengiriman",
	"akhir_tanggal_pengiriman",
)


def akar_do_pecahan(delivery_order):
	"""DO paling awal dari rantai pecahan, supaya pecahan dari 051A jadi 051B, bukan 051AA."""
	akar = delivery_order
	for _i in range(50):
		induk = frappe.db.get_value("Delivery Order", akar, "pecahan_dari")
		if not induk:
			break
		akar = induk

	return akar


def urutan_huruf():
	"""A..Z, lalu AA..AZ, BA.. dan seterusnya."""
	huruf = [chr(kode) for kode in range(ord("A"), ord("Z") + 1)]
	yield from huruf
	for depan in huruf:
		for belakang in huruf:
			yield depan + belakang


def nama_do_pecahan(pecahan_dari):
	akar = akar_do_pecahan(pecahan_dari)
	# DO pecahan yang dibatalkan namanya tetap terpakai, jadi yang dicek nama
	# yang ada di tabel, bukan jumlah pecahan yang masih hidup.
	for huruf in urutan_huruf():
		nama = akar + huruf
		if not frappe.db.exists("Delivery Order", nama):
			return nama

	frappe.throw(_("Nomor pecahan untuk DO {0} sudah habis.").format(akar))


def qty_terpakai_do(delivery_order, item_code, delivered_qty=0):
	"""Qty DO yang sudah dipakai dan tidak boleh dilepas waktu DO dipecah.

	Diambil yang terbesar dari dua basis: yang sudah jadi Delivery Note
	(delivered_qty) dan yang sudah dibebankan timbangan, termasuk timbangan draft
	yang truknya masih di dalam. Basis timbangannya sama dengan
	Timbangan.get_sisa_do_available supaya DO yang dipecah tidak langsung menolak
	timbangan yang sedang berjalan.
	"""
	qty_timbangan = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(CASE WHEN COALESCE(no_do_2, '') = '' THEN COALESCE(netto_2, 0)
					   ELSE COALESCE(qty_do, 0) END), 0)
		FROM `tabTimbangan`
		WHERE do_no = %(do)s AND kode_barang = %(item)s AND docstatus != 2
		""",
		{"do": delivery_order, "item": item_code},
	)[0][0]

	qty_timbangan_2 = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(qty_do_2), 0)
		FROM `tabTimbangan`
		WHERE no_do_2 = %(do)s AND kode_barang = %(item)s AND docstatus != 2
		""",
		{"do": delivery_order, "item": item_code},
	)[0][0]

	return max(flt(delivered_qty), flt(qty_timbangan) + flt(qty_timbangan_2))


@frappe.whitelist()
def get_data_pecah_do(delivery_order):
	"""Qty tiap baris DO beserta yang sudah terpakai, untuk dialog Pecah DO."""
	doc = frappe.get_doc("Delivery Order", delivery_order)
	doc.check_permission("read")

	return [
		{
			"name": item.name,
			"item_code": item.item_code,
			"item_name": item.item_name,
			"uom": item.uom,
			"qty": flt(item.qty),
			"delivered_qty": flt(item.delivered_qty),
			"terpakai": qty_terpakai_do(doc.name, item.item_code, item.delivered_qty),
		}
		for item in doc.items
	]


@frappe.whitelist()
def pecah_delivery_order(delivery_order, qty_baru):
	"""Kurangi qty DO yang sudah disubmit supaya sisanya bisa ditarik jadi DO pecahan.

	Pengganti "unpost" di program lama: DO tidak dibatalkan (DN, timbangan, dan
	QR-nya tetap menempel), cuma qty-nya diturunkan sampai paling rendah qty yang
	sudah terpakai. Sisa yang dilepas kembali jadi sisa kontrak, sehingga DO
	berikutnya yang ditarik dari Sales Order yang sama otomatis mendapat sisanya.
	"""
	qty_baru = frappe.parse_json(qty_baru) or {}

	doc = frappe.get_doc("Delivery Order", delivery_order)
	# Mengubah DO yang sudah terbit setara dengan membatalkannya, jadi yang boleh
	# hanya yang berhak submit.
	doc.check_permission("submit")

	if doc.docstatus != 1:
		frappe.throw(_("Hanya DO yang sudah disubmit yang bisa dipecah."))

	berubah = []
	for item in doc.items:
		if item.name not in qty_baru:
			continue

		lama = flt(item.qty)
		baru = flt(qty_baru[item.name], item.precision("qty"))
		if baru == lama:
			continue

		if baru > lama:
			frappe.throw(
				_("Baris {0}: qty baru {1} lebih besar dari qty DO {2}. Pecah DO hanya bisa mengurangi.").format(
					item.idx, baru, lama
				)
			)

		terpakai = qty_terpakai_do(doc.name, item.item_code, item.delivered_qty)
		if baru < terpakai:
			frappe.throw(
				_("Baris {0} ({1}): qty baru {2} lebih kecil dari yang sudah terpakai {3} (Delivery Note / timbangan).").format(
					item.idx, item.item_code, baru, terpakai
				)
			)

		item.qty = baru
		item.stock_qty = flt(baru * flt(item.conversion_factor or 1), item.precision("stock_qty"))
		berubah.append((item, lama, baru))

	if not berubah:
		frappe.throw(_("Tidak ada qty yang berubah."))

	doc.calculate_taxes_and_totals()
	if hasattr(doc, "set_total_in_words"):
		doc.set_total_in_words()

	doc.modified = frappe.utils.now()
	doc.modified_by = frappe.session.user
	doc.db_update_all()

	doc.add_comment(
		"Info",
		_("DO dipecah: {0}").format(
			", ".join(
				"{0} {1} -> {2} (dilepas {3})".format(item.item_code, lama, baru, flt(lama - baru))
				for item, lama, baru in berubah
			)
		),
	)

	update_per_delivery_ordered_on_submit_cancel(doc, "pecah_do")
	for item, _lama, _baru in berubah:
		perbarui_sisa_do_timbangan(doc.name, item.item_code)

	return {"dilepas": sum(flt(lama - baru) for _item, lama, baru in berubah)}


@frappe.whitelist()
def make_do_pecahan(source_name, target_doc=None):
	"""DO baru dari kontrak yang sama untuk menampung sisa DO yang sudah dipecah.

	Itemnya ditarik lewat Sales Order seperti DO biasa, jadi qty-nya otomatis sisa
	kontrak; yang diambil hanya baris kontrak milik DO asalnya.
	"""
	induk = frappe.get_doc("Delivery Order", source_name)
	induk.check_permission("read")

	if induk.docstatus != 1:
		frappe.throw(_("DO {0} belum disubmit.").format(induk.name))

	sales_order = induk.sales_order or next(
		(item.against_sales_order for item in induk.items if item.against_sales_order), None
	)
	if not sales_order:
		frappe.throw(_("DO {0} tidak ditarik dari kontrak, jadi sisanya tidak bisa dibuat DO pecahan.").format(induk.name))

	baris_induk = {item.so_detail: item for item in induk.items if item.so_detail}

	target = make_delivery_order(sales_order, target_doc)
	target.set("items", [item for item in target.get("items") if item.so_detail in baris_induk])

	if not target.get("items"):
		frappe.throw(
			_("Kontrak {0} tidak punya sisa untuk barang DO {1}. Kurangi dulu qty DO lewat tombol Pecah DO.").format(
				sales_order, induk.name
			)
		)

	target.pecahan_dari = induk.name
	for fieldname in FIELD_IKUT_INDUK:
		if induk.get(fieldname):
			target.set(fieldname, induk.get(fieldname))

	for item in target.items:
		asal = baris_induk[item.so_detail]
		if asal.warehouse:
			item.warehouse = asal.warehouse

	if induk.get("keterangan_per_komoditi"):
		target.set("keterangan_per_komoditi", [])
		for row in induk.keterangan_per_komoditi:
			target.append("keterangan_per_komoditi", row.as_dict(no_default_fields=True))

	for idx, item in enumerate(target.items, start=1):
		item.idx = idx

	return target


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
