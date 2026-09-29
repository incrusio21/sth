# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

"""Mengganti rate masuk Stock Entry yang sudah disubmit, lalu menilai ulang
Stock Ledger sesudahnya.

Dipakai COGS Mill dan Kebun untuk membebankan HPP bulan itu ke semua barang
yang masuk dan keluar, dan oleh gudang transit untuk menyamakan penerimaannya
dengan nilai keluar Delivery Note.

Yang diganti cuma rate barang masuk. Nilai barang keluar tidak pernah ditimpa
langsung: Repost Item Valuation menghitung ulang nilai keluar dari rate masuk
setiap kali ada transaksi mundur, jadi nilai keluar yang ditimpa sendiri akan
tertimpa balik diam-diam. Sebaliknya rate Material Receipt dianggap ketetapan
dan tidak pernah dihitung ulang repost, karena itu justru rate itu yang diganti
di sini.
"""

import frappe
from erpnext.stock.doctype.repost_item_valuation.repost_item_valuation import repost
from frappe.utils import flt

WAKTU_AWAL_HARI = "00:00:00"


def ganti_rate_masuk(stock_entry, rate_per_baris):
	"""Ganti basic_rate baris masuk Stock Entry yang sudah disubmit.

	rate_per_baris berbentuk {nama Stock Entry Detail: rate baru}. Stock Ledger
	Entry baris itu ikut diganti incoming_rate-nya, tapi saldo sesudahnya belum
	bergeser sampai repost_item_gudang dijalankan. Mengembalikan pasangan
	(item, gudang) yang rate-nya diganti.
	"""
	se = frappe.get_doc("Stock Entry", stock_entry)

	berubah = set()
	for d in se.items:
		if d.name not in rate_per_baris or not d.t_warehouse or d.s_warehouse:
			continue
		d.basic_rate = flt(rate_per_baris[d.name])
		d.basic_amount = flt(flt(d.transfer_qty) * d.basic_rate, d.precision("basic_amount"))
		berubah.add((d.item_code, d.t_warehouse))

	if not berubah:
		return berubah

	# Urutan yang sama dengan calculate_rate_and_amount, minus set_basic_rate:
	# yang itu akan mengisi ulang rate dari valuasi gudang.
	se.distribute_additional_costs()
	se.update_valuation_rate()
	se.set_total_incoming_outgoing_value()
	se.set_total_amount()

	for d in se.items:
		d.db_update()
	se.db_update()

	for d in se.items:
		if d.name not in rate_per_baris:
			continue
		frappe.db.sql("""
			update `tabStock Ledger Entry`
			set incoming_rate = %s
			where voucher_type = 'Stock Entry' and voucher_no = %s and voucher_detail_no = %s
				and is_cancelled = 0 and actual_qty > 0
		""", (flt(d.valuation_rate), se.name, d.name))

	return berubah


def repost_item_gudang(pasangan, company, dari):
	"""Nilai ulang Stock Ledger dan GL tiap pasangan item-gudang sejak awal
	tanggal `dari`, sekarang juga, bukan menunggu scheduler.

	Repost Item Valuation-nya tetap dibuat sebagai dokumen supaya jejaknya sama
	dengan repost biasa, tapi langsung dijalankan: langkah sesudahnya butuh
	nilai yang sudah bergeser. Fungsi repost ERPNext menelan galatnya sendiri
	dan cuma menulis status, jadi statusnya diperiksa lagi di sini.

	Fungsi repost itu melakukan commit sendiri, jadi pemanggilnya harus siap
	dijalankan ulang dari tengah.
	"""
	for item_code, warehouse in sorted(pasangan):
		riv = frappe.new_doc("Repost Item Valuation")
		riv.based_on = "Item and Warehouse"
		riv.item_code = item_code
		riv.warehouse = warehouse
		riv.company = company
		riv.posting_date = dari
		riv.posting_time = WAKTU_AWAL_HARI
		# Stok yang sempat minus di tengah riwayat tidak boleh menggagalkan
		# seluruh revaluasi. Landed Cost Voucher ERPNext melakukan hal yang sama.
		riv.allow_negative_stock = 1
		riv.flags.ignore_links = True
		riv.flags.ignore_permissions = True
		riv.insert()
		riv.submit()
		frappe.db.commit()

		repost(riv)

		status, galat = frappe.db.get_value(
			"Repost Item Valuation", riv.name, ["status", "error_log"]
		)
		if status != "Completed":
			frappe.throw(
				"Repost Item Valuation <b>{0}</b> untuk {1} di {2} berhenti dengan status "
				"<b>{3}</b>.<br><br>{4}".format(
					riv.name, item_code, warehouse, status, (galat or "")[:2000]
				)
			)

		# Repost yang masih antre untuk pasangan yang sama sesudah titik ini sudah
		# tercakup, jadi dilewati — sama dengan yang dilakukan scheduler ERPNext.
		riv.deduplicate_similar_repost()
		frappe.db.commit()
