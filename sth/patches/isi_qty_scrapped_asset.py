import frappe
from frappe.utils import cint, flt

STATE_APPROVED = "Approved"


def execute():
	"""Catat qty_scrapped untuk asset yang discrap penuh, lalu bebaskan yang tersangkut.

	Sebelumnya scrap penuh tidak mengisi qty_scrapped sama sekali — kelayakan jual
	disimpulkan dari status == "Scrapped". Status itu berubah jadi "Sold" waktu
	asetnya dijual dan tidak pernah dikembalikan waktu invoicenya dibatalkan, jadi
	asetnya berhenti di status Sold dengan qty_scrapped 0 dan tidak bisa dijual
	lagi selamanya.

	Sesudah ini qty_scrapped jadi satu-satunya sumber kebenaran, sehingga status
	asset boleh berubah-ubah tanpa mempengaruhi hak jualnya.
	"""
	isi_qty_scrapped()
	bebaskan_asset_tersangkut()


def isi_qty_scrapped():
	"""Asset yang punya Asset Scrap Request disetujui tapi qty_scrapped-nya masih 0."""
	pengajuan = frappe.db.sql("""
		SELECT asr.asset, asr.asset_quantity, asr.persentase_scrap, a.asset_quantity AS qty_asset
		FROM `tabAsset Scrap Request` asr
		JOIN `tabAsset` a ON a.name = asr.asset
		WHERE asr.docstatus = 1
		  AND COALESCE(asr.workflow_state, %(approved)s) = %(approved)s
		  AND asr.persentase_scrap >= 100
		  AND COALESCE(a.qty_scrapped, 0) = 0
	""", {"approved": STATE_APPROVED}, as_dict=True)

	for row in pengajuan:
		qty = cint(row.asset_quantity) or cint(row.qty_asset) or 1
		frappe.db.set_value("Asset", row.asset, "qty_scrapped", qty, update_modified=False)


def bebaskan_asset_tersangkut():
	"""Asset berstatus Sold yang seluruh Sales Invoice Disposal-nya sudah dibatalkan.

	Statusnya dihitung ulang lewat set_status() supaya asetnya kembali ke status
	yang wajar, dan disposal_date dikosongkan karena penjualannya tidak jadi.
	"""
	tersangkut = frappe.db.sql_list("""
		SELECT DISTINCT sii.asset
		FROM `tabSales Invoice Item` sii
		JOIN `tabSales Invoice` si ON si.name = sii.parent
		JOIN `tabAsset` a ON a.name = sii.asset
		WHERE si.jenis_penagihan = 'Disposal'
		  AND si.docstatus = 2
		  AND a.docstatus = 1
		  AND a.status = 'Sold'
		  AND NOT EXISTS (
			  SELECT 1
			  FROM `tabSales Invoice Item` sii2
			  JOIN `tabSales Invoice` si2 ON si2.name = sii2.parent
			  WHERE sii2.asset = sii.asset
				AND si2.jenis_penagihan = 'Disposal'
				AND si2.docstatus != 2
		  )
	""")

	for nama in tersangkut:
		asset = frappe.get_doc("Asset", nama)
		asset.db_set("disposal_date", None, update_modified=False)
		asset.set_status()
