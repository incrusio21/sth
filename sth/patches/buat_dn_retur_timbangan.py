import frappe
from frappe.utils import cint

from sth.mill.doctype.timbangan.timbangan import cari_delivery_note_asal, get_baris_dn_asal


def execute(terapkan=0, nama=None, dn_asal=None):
	"""Buat DN Return untuk Timbangan Return submitted yang belum punya.

	Sebelum Timbangan Return membuat DN Return sendiri, submit-nya tidak menulis
	apa-apa ke DO, Sales Order, maupun stok. Sisa DO menurut timbangan sudah
	bertambah sebesar netto returnya, tapi delivered_qty Sales Order Item tidak,
	sehingga DN Dispatch berikutnya atas DO yang sama ditolak "Limit Crossed".

	DN asalnya dicocokkan seperti saat submit (cari_delivery_note_asal). Yang
	tidak ketemu dilaporkan; jalankan ulang untuk timbangan itu dengan
	`nama` dan `dn_asal`.

	    bench --site <site> execute sth.patches.buat_dn_retur_timbangan.execute
	    bench --site <site> execute sth.patches.buat_dn_retur_timbangan.execute \\
	        --kwargs "{'terapkan': 1}"
	    bench --site <site> execute sth.patches.buat_dn_retur_timbangan.execute \\
	        --kwargs "{'terapkan': 1, 'nama': 'TBG-00001', 'dn_asal': 'MAT-DN-2026-00001'}"

	Patch ini aman diulang: timbangan yang DN Return-nya sudah submitted dilewati.
	"""
	terapkan = cint(terapkan)
	print("Mode {0}\n".format("TERAPKAN" if terapkan else "LAPORAN SAJA"))

	filters = {"type": "Return", "docstatus": 1, "do_no": ["is", "set"]}
	if nama:
		filters["name"] = nama

	for name in frappe.get_all("Timbangan", filters=filters, pluck="name", order_by="posting_date, creation"):
		doc = frappe.get_doc("Timbangan", name)
		if not doc.perlu_dn_retur():
			continue
		if doc.delivery_note and frappe.db.get_value("Delivery Note", doc.delivery_note, "docstatus") == 1:
			continue

		asal = (dn_asal if nama else None) or doc.delivery_note_asal or cari_delivery_note_asal(doc)
		if not asal or not get_baris_dn_asal(doc, asal):
			print(f"{name}: DO {doc.do_no}, {doc.qty_retur()} — DN asal tidak ketemu, lewati")
			continue

		print(f"{name}: DO {doc.do_no}, {doc.qty_retur()} — retur atas {asal}")
		if not terapkan:
			continue

		doc.db_set("delivery_note_asal", asal)
		doc.create_delivery_note_retur()
		frappe.db.commit()
		print(f"  -> {doc.delivery_note}")
