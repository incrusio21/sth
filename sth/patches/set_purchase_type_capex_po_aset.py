import frappe


def execute(dry_run=False):
	"""Ubah purchase_type PO jadi Capex kalau baris pertamanya aset tetap.

	make_purchase_order dari Supplier Quotation dulu menentukan tipe sebelum
	is_fixed_asset baris PO terisi (Supplier Quotation Item tidak punya field
	itu), jadi semua PO dari SQ jatuh ke Non Capex. Patokannya sama dengan kode
	yang sudah dibetulkan: is_fixed_asset di master Item untuk baris idx 1.

	Purchase Receipt yang sudah terbentuk tidak disentuh. Tipenya diambil dari
	future_type PO saat dibuat (Non Capex -> Berita Acara), dan PR berikutnya
	dari PO yang sudah Capex akan bertipe future_type Capex.

	    bench --site <site> execute sth.patches.set_purchase_type_capex_po_aset.execute --kwargs "{'dry_run': 1}"
	"""
	po_list = frappe.db.sql(
		"""
		SELECT po.name, po.docstatus, po.status, po.company, poi.item_code
		FROM `tabPurchase Order` po
		JOIN `tabPurchase Order Item` poi ON poi.parent = po.name AND poi.idx = 1
		JOIN `tabItem` i ON i.name = poi.item_code
		WHERE po.docstatus < 2
		  AND po.purchase_type = 'Non Capex'
		  AND i.is_fixed_asset = 1
		ORDER BY po.transaction_date, po.name
		""",
		as_dict=True,
	)

	for po in po_list:
		pr = frappe.db.sql_list(
			"""
			SELECT DISTINCT CONCAT(pr.name, ' (', pr.purchase_type, ')')
			FROM `tabPurchase Receipt Item` pri
			JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
			WHERE pri.purchase_order = %s AND pr.docstatus < 2
			""",
			po.name,
		)
		print(
			f"{po.name} [{po.status}] {po.company} {po.item_code} -> Capex"
			+ (f"; PR tetap: {', '.join(pr)}" if pr else "")
		)

	if not dry_run and po_list:
		frappe.db.sql(
			"""
			UPDATE `tabPurchase Order`
			SET purchase_type = 'Capex'
			WHERE name IN %(nama)s
			""",
			{"nama": [po.name for po in po_list]},
		)
		frappe.db.commit()

	print(f"{len(po_list)} PO {'akan diubah' if dry_run else 'diubah'} ke Capex")
