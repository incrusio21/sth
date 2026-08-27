# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

"""Gudang transit CPO dan Palm Kernel.

Alurnya:

	Timbangan Dispatch   -> Delivery Note, keluar dari gudang default item
	Delivery Note submit -> Stock Entry Material Receipt ke gudang transit,
	                        ditandai Delivery Note-nya
	Sales Invoice submit -> Stock Entry Material Issue dari gudang transit,
	                        sebanyak yang ditagih dari Delivery Note itu

Nilainya tidak dobel karena Delivery Note memang sudah tidak membebankan harga
pokok: update_ke_stock_in_transit_account mengisi expense account tiap barisnya
dengan Stock In Transit Account. Material Receipt memakai akun yang sama sebagai
lawan jurnal, jadi debit yang ditinggalkan Delivery Note di akun itu langsung
dikreditkan balik dan nilainya berpindah ke akun persediaan gudang transit.
Harga pokok penjualan baru lahir waktu Material Issue dibuat dari Sales Invoice.

Yang ikut alur ini cuma item yang terdaftar di STH Stock Settings tab Transit.
Item lain keluar langsung lewat Delivery Note seperti sebelumnya.
"""

import erpnext
import frappe
from frappe import _
from frappe.utils import flt, get_link_to_form

PURPOSE_MASUK = "Material Receipt"
PURPOSE_KELUAR = "Material Issue"

KETERANGAN_MASUK = "Penerimaan gudang transit dari Delivery Note {0}"
KETERANGAN_KELUAR = "Pengeluaran gudang transit untuk Sales Invoice {0}"


# ---------------------------------------------------------------------------
# Setelan
# ---------------------------------------------------------------------------

def get_setelan_transit(company):
	"""Gudang transit dan akun lawannya untuk satu company.

	Dua-duanya dari tabel yang sama yang sudah dipakai Delivery Note, supaya
	akun yang didebit Delivery Note dan yang dikredit Material Receipt dijamin
	akun yang sama.
	"""
	settings = frappe.get_single("STH Stock Settings")

	for row in settings.sth_stock_settings_table:
		if row.company == company:
			return frappe._dict({
				"warehouse": row.transit_warehouse,
				"account": row.stock_in_transit_account,
			})

	return frappe._dict({"warehouse": None, "account": None})


def get_item_transit(company):
	"""Item yang mampir di gudang transit, untuk satu company."""
	settings = frappe.get_single("STH Stock Settings")

	return {
		row.item_code
		for row in settings.sth_stock_settings_item_transit
		if row.company == company and row.item_code
	}


def baris_transit(doc):
	"""Baris item dokumen yang ikut alur gudang transit."""
	item_transit = get_item_transit(doc.company)
	if not item_transit:
		return []

	return [d for d in doc.items if d.item_code in item_transit]


def setelan_wajib(company, dokumen):
	setelan = get_setelan_transit(company)

	if not setelan.warehouse:
		frappe.throw(_(
			"Gudang Transit untuk company {0} belum diisi di STH Stock Settings tab "
			"Transit, padahal {1} memuat item yang terdaftar lewat gudang transit."
		).format(company, dokumen))

	if not setelan.account:
		frappe.throw(_(
			"Stock In Transit Account untuk company {0} belum diisi di STH Stock "
			"Settings tab Transit."
		).format(company))

	return setelan


# ---------------------------------------------------------------------------
# Delivery Note -> masuk gudang transit
# ---------------------------------------------------------------------------

def buat_penerimaan_transit(doc, method=None):
	"""Terima barang Delivery Note ini di gudang transit.

	Dipanggil sesudah Delivery Note disubmit, jadi Stock Ledger Entry-nya sudah
	ada dan nilai keluarnya bisa dipakai apa adanya sebagai nilai masuk.
	"""
	if doc.docstatus != 1 or doc.get("is_return") or doc.get("is_internal_customer"):
		return

	if stock_entry_transit(delivery_note=doc.name, purpose=PURPOSE_MASUK):
		return

	baris = baris_transit(doc)
	if not baris:
		return

	setelan = setelan_wajib(doc.company, _("Delivery Note {0}").format(doc.name))

	se = frappe.new_doc("Stock Entry")
	se.company = doc.company
	se.purpose = PURPOSE_MASUK
	se.stock_entry_type = PURPOSE_MASUK
	se.set_posting_time = 1
	se.posting_date = doc.posting_date
	se.posting_time = doc.posting_time
	se.delivery_note_transit = doc.name
	se.remarks = KETERANGAN_MASUK.format(doc.name)

	if doc.get("unit") and se.meta.has_field("unit"):
		se.unit = doc.unit

	for item in baris:
		rate = nilai_keluar_dn(doc.name, item.name)
		se.append("items", {
			"item_code": item.item_code,
			"t_warehouse": setelan.warehouse,
			"qty": abs(flt(item.stock_qty)),
			"uom": item.stock_uom,
			"stock_uom": item.stock_uom,
			"conversion_factor": 1,
			"basic_rate": rate,
			# Nilai keluar Delivery Note bisa nol kalau itemnya memang belum
			# punya valuasi. Ikut nol supaya jurnalnya tetap sepadan dengan
			# Delivery Note-nya, bukan ditolak di tengah jalan penimbangan.
			"allow_zero_valuation_rate": 0 if rate else 1,
			"expense_account": setelan.account,
			"cost_center": cost_center_baris(item, doc.company),
			"delivery_note_transit": doc.name,
			"delivery_note_item_transit": item.name,
		})

	se.flags.ignore_permissions = True
	se.insert()
	se.submit()

	frappe.msgprint(
		_("Stock Entry {0} dibuat: barang masuk gudang transit {1}.").format(
			get_link_to_form("Stock Entry", se.name), setelan.warehouse
		),
		indicator="green",
		alert=True,
	)

	return se.name


def nilai_keluar_dn(delivery_note, dn_item):
	"""Nilai per satuan yang benar-benar keluar dari gudang default.

	Diambil dari Stock Ledger Entry Delivery Note-nya, bukan dari rate jual,
	supaya nilai yang masuk gudang transit persis sebesar nilai yang keluar.
	"""
	sle = frappe.db.get_value(
		"Stock Ledger Entry",
		{
			"voucher_type": "Delivery Note",
			"voucher_no": delivery_note,
			"voucher_detail_no": dn_item,
			"is_cancelled": 0,
		},
		["sum(stock_value_difference) as nilai", "sum(actual_qty) as qty"],
		as_dict=True,
	)

	if sle and flt(sle.qty):
		return abs(flt(sle.nilai) / flt(sle.qty))

	# Delivery Note tanpa dampak stok tidak meninggalkan Stock Ledger Entry;
	# pakai incoming rate barisnya sendiri.
	return abs(flt(frappe.db.get_value("Delivery Note Item", dn_item, "incoming_rate")))


def batalkan_penerimaan_transit(doc, method=None):
	"""Batalkan penerimaan transit waktu Delivery Note-nya dibatalkan."""
	batalkan_stock_entry_transit(
		stock_entry_transit(delivery_note=doc.name, purpose=PURPOSE_MASUK)
	)


# ---------------------------------------------------------------------------
# Sales Invoice -> keluar gudang transit
# ---------------------------------------------------------------------------

def buat_pengeluaran_transit(doc, method=None):
	"""Keluarkan barang dari gudang transit sebanyak yang ditagih invoice ini.

	Yang dikeluarkan cuma baris yang menunjuk Delivery Note, karena stok
	transitnya memang lahir dari Delivery Note. Baris invoice tanpa Delivery
	Note tidak menyentuh gudang transit.
	"""
	if doc.docstatus != 1 or doc.get("is_return"):
		return

	if stock_entry_transit(sales_invoice=doc.name, purpose=PURPOSE_KELUAR):
		return

	baris = [d for d in baris_transit(doc) if d.get("delivery_note")]
	if not baris:
		return

	setelan = setelan_wajib(doc.company, _("Sales Invoice {0}").format(doc.name))
	akun_beban = akun_harga_pokok(doc.company)

	se = frappe.new_doc("Stock Entry")
	se.company = doc.company
	se.purpose = PURPOSE_KELUAR
	se.stock_entry_type = PURPOSE_KELUAR
	se.set_posting_time = 1
	se.posting_date = doc.posting_date
	se.posting_time = doc.posting_time
	se.sales_invoice_transit = doc.name
	se.remarks = KETERANGAN_KELUAR.format(doc.name)

	if doc.get("unit") and se.meta.has_field("unit"):
		se.unit = doc.unit

	for item in baris:
		qty = abs(flt(item.stock_qty))
		if not qty:
			continue

		validasi_sisa_transit(item, qty)

		se.append("items", {
			"item_code": item.item_code,
			"s_warehouse": setelan.warehouse,
			"qty": qty,
			"uom": item.stock_uom,
			"stock_uom": item.stock_uom,
			"conversion_factor": 1,
			"expense_account": akun_beban,
			"cost_center": cost_center_baris(item, doc.company),
			"delivery_note_transit": item.delivery_note,
			"delivery_note_item_transit": item.get("dn_detail"),
		})

	if not se.items:
		return

	se.flags.ignore_permissions = True
	se.insert()
	se.submit()

	frappe.msgprint(
		_("Stock Entry {0} dibuat: barang keluar dari gudang transit {1}.").format(
			get_link_to_form("Stock Entry", se.name), setelan.warehouse
		),
		indicator="green",
		alert=True,
	)

	return se.name


def cost_center_baris(item, company):
	"""Cost center baris, jatuh ke default company kalau dokumen sumbernya kosong.

	Akun harga pokok itu akun laba rugi, dan ERPNext menolak Stock Entry dengan
	akun laba rugi tanpa cost center.
	"""
	return item.get("cost_center") or erpnext.get_default_cost_center(company)


def akun_harga_pokok(company):
	"""Akun beban waktu barang benar-benar dilepas dari gudang transit."""
	akun = frappe.get_cached_value("Company", company, "default_expense_account")
	if not akun:
		frappe.throw(_(
			"Default Cost of Goods Sold Account untuk company {0} belum diisi, "
			"padahal dipakai membebankan barang yang keluar dari gudang transit."
		).format(company))

	return akun


def validasi_sisa_transit(item, qty):
	"""Tolak penagihan yang melebihi barang yang masih ada di gudang transit.

	Kalau dibiarkan, yang gagal adalah Stock Entry-nya dengan pesan stok negatif,
	dan Delivery Note mana yang kurang tidak kelihatan.
	"""
	sisa = sisa_transit(item.delivery_note, item.item_code)

	if flt(qty, 3) > flt(sisa, 3):
		frappe.throw(_(
			"Item {0} dari Delivery Note {1} ditagih {2} tapi sisa di gudang transit "
			"tinggal {3}. Periksa qty invoice atau Stock Entry transit yang sudah "
			"terlanjur dibuat."
		).format(item.item_code, item.delivery_note, flt(qty, 3), flt(sisa, 3)))


def sisa_transit(delivery_note, item_code):
	"""Barang satu Delivery Note yang masih menumpuk di gudang transit."""
	masuk, keluar = 0, 0

	rows = frappe.db.sql("""
		SELECT se.purpose, SUM(sed.transfer_qty) AS qty
		FROM `tabStock Entry` se
		JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
		WHERE se.docstatus = 1
		  AND sed.delivery_note_transit = %(dn)s
		  AND sed.item_code = %(item_code)s
		GROUP BY se.purpose
	""", {"dn": delivery_note, "item_code": item_code}, as_dict=True)

	for r in rows:
		if r.purpose == PURPOSE_MASUK:
			masuk += flt(r.qty)
		elif r.purpose == PURPOSE_KELUAR:
			keluar += flt(r.qty)

	return masuk - keluar


def batalkan_pengeluaran_transit(doc, method=None):
	"""Kembalikan barang ke gudang transit waktu invoicenya dibatalkan."""
	batalkan_stock_entry_transit(
		stock_entry_transit(sales_invoice=doc.name, purpose=PURPOSE_KELUAR)
	)


# ---------------------------------------------------------------------------
# Umum
# ---------------------------------------------------------------------------

def stock_entry_transit(delivery_note=None, sales_invoice=None, purpose=None):
	"""Stock Entry transit yang masih hidup untuk satu dokumen sumber."""
	filters = {"docstatus": ["<", 2]}

	if delivery_note:
		filters["delivery_note_transit"] = delivery_note
	if sales_invoice:
		filters["sales_invoice_transit"] = sales_invoice
	if purpose:
		filters["purpose"] = purpose

	return frappe.get_all("Stock Entry", filters=filters, pluck="name")


def batalkan_stock_entry_transit(names):
	"""Batalkan Stock Entry transit sebelum dokumen sumbernya ikut dibatalkan.

	Dijalankan di on_cancel, yang di Frappe berjalan sebelum pemeriksaan dokumen
	tertaut, jadi Stock Entry ini sudah berstatus Cancelled waktu pemeriksaan itu
	sampai giliran.
	"""
	for name in names:
		se = frappe.get_doc("Stock Entry", name)
		if se.docstatus == 1:
			se.flags.ignore_permissions = True
			se.cancel()
		elif se.docstatus == 0:
			se.delete(ignore_permissions=True)
