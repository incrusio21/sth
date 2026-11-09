import frappe
from erpnext.stock.stock_balance import get_ordered_qty, update_bin_qty
from frappe.utils import cint


def execute(terapkan=0, nama=None):
	"""Samakan gudang baris Purchase Order hasil Supplier Quotation dengan Set Target Warehouse.

	PO yang dibuat dari Supplier Quotation (create_po_draft / make_purchase_order)
	mengisi set_warehouse di header dengan gudang central unit, tapi barisnya masih
	membawa gudang dari Material Request. Purchase Receipt mengambil gudang dari
	baris PO, jadi barang diterima ke gudang Material Request, bukan gudang central.

	Yang diperbaiki hanya baris PO yang berasal dari Supplier Quotation, belum
	diterima penuh, pada PO draft/submitted yang belum Closed/Completed. Baris
	Purchase Receipt draft yang menunjuk baris itu dan masih memakai gudang lama
	ikut disamakan. Purchase Receipt yang sudah submitted tidak disentuh.

	    bench --site <site> execute sth.patches.samakan_gudang_baris_po.execute
	    bench --site <site> execute sth.patches.samakan_gudang_baris_po.execute \\
	        --kwargs "{'terapkan': 1}"
	    bench --site <site> execute sth.patches.samakan_gudang_baris_po.execute \\
	        --kwargs "{'terapkan': 1, 'nama': 'PO-TPRM-09-2026-00074'}"

	Patch ini aman diulang: baris yang gudangnya sudah sama dilewati.
	"""
	terapkan = cint(terapkan)
	print("Mode {0}\n".format("TERAPKAN" if terapkan else "LAPORAN SAJA"))

	kondisi_nama = "AND po.name = %(nama)s" if nama else ""

	baris_po = frappe.db.sql(
		"""
		SELECT po.name AS po, po.set_warehouse, poi.name AS poi, poi.idx,
			poi.item_code, poi.warehouse
		FROM `tabPurchase Order Item` poi
		JOIN `tabPurchase Order` po ON po.name = poi.parent
		WHERE po.docstatus < 2
			AND po.status NOT IN ('Closed', 'Completed')
			AND IFNULL(po.set_warehouse, '') != ''
			AND IFNULL(poi.supplier_quotation, '') != ''
			AND IFNULL(poi.warehouse, '') != po.set_warehouse
			AND poi.received_qty < poi.qty
			{0}
		ORDER BY po.name, poi.idx
		""".format(kondisi_nama),
		{"nama": nama},
		as_dict=1,
	)

	if not baris_po:
		print("Tidak ada baris PO yang perlu diperbaiki.")
		return

	jumlah_prec = 0
	for row in baris_po:
		print("{0} #{1} {2}: {3} -> {4}".format(
			row.po, row.idx, row.item_code, row.warehouse or "-", row.set_warehouse
		))

		baris_prec = frappe.get_all(
			"Purchase Receipt Item",
			filters={
				"purchase_order_item": row.poi,
				"docstatus": 0,
				"warehouse": row.warehouse,
			},
			fields=["name", "parent"],
		)
		for prec in baris_prec:
			print("    PREC draft {0}: {1} -> {2}".format(prec.parent, row.warehouse, row.set_warehouse))

		jumlah_prec += len(baris_prec)

		if not terapkan:
			continue

		frappe.db.set_value(
			"Purchase Order Item", row.poi, "warehouse", row.set_warehouse, update_modified=False
		)
		for prec in baris_prec:
			frappe.db.set_value(
				"Purchase Receipt Item", prec.name, "warehouse", row.set_warehouse, update_modified=False
			)

	if terapkan:
		# ordered_qty di Bin dihitung dari gudang baris PO submitted; set_value tidak
		# menyentuh Bin, jadi gudang lama dan baru dihitung ulang.
		for item_code, gudang in {
			(row.item_code, wh) for row in baris_po for wh in (row.warehouse, row.set_warehouse) if wh
		}:
			update_bin_qty(item_code, gudang, {"ordered_qty": get_ordered_qty(item_code, gudang)})

	print("\n{0} baris PO, {1} baris PREC draft{2}.".format(
		len(baris_po), jumlah_prec, " diperbaiki" if terapkan else " akan diperbaiki"
	))

	if terapkan:
		frappe.db.commit()
