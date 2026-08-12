import frappe
from frappe import _
from frappe.utils import cint

VOUCHER_PENYUSUTAN = "Depreciation Entry"


def cegah_penyusutan_ganda(doc, method=None):
	"""Tolak jurnal penyusutan untuk asset dan tanggal yang sudah dibukukan.

	Satu asset boleh punya satu jurnal penyusutan per tanggal per finance book —
	tidak lebih. Batas itu pernah jebol: pelepasan yang dibatalkan tidak mereset
	depreciation schedule, sehingga pelepasan berikutnya memanggil
	depreciate_asset() dan memposting ulang seluruh baris schedule yang belum
	punya JE, termasuk bulan yang sudah dibukukan. Pada satu asset polanya
	terulang enam kali sebelum ketahuan.

	Lubang itu sudah ditutup di sisi pembatalan Sales Invoice Disposal, tapi
	penjaga ini tetap dipasang: penyusutan menumpuk diam-diam di buku besar dan
	baru terlihat berbulan-bulan kemudian. Kalau ada jalur lain yang belum
	ketahuan, lebih baik submitnya gagal sekarang daripada bebannya berlipat.

	Jurnal pembalik dikecualikan — membalik penyusutan justru yang dibutuhkan
	waktu pelepasan dibatalkan.
	"""
	if doc.voucher_type != VOUCHER_PENYUSUTAN:
		return

	if frappe.flags.get("is_reverse_depr_entry") or doc.get("is_opening") == "Yes":
		return

	for asset in _asset_di_jurnal(doc):
		batas = _jumlah_finance_book(asset)
		sudah = _jumlah_penyusutan_aktif(asset, doc.posting_date, doc.name)

		if sudah < batas:
			continue

		frappe.throw(
			_(
				"Asset {0} sudah punya {1} jurnal penyusutan aktif bertanggal {2}. "
				"Penyusutan yang sama tidak boleh dibukukan dua kali — batalkan dulu "
				"jurnal yang lama kalau memang mau dibukukan ulang."
			).format(
				frappe.bold(asset),
				sudah,
				frappe.format_value(doc.posting_date, {"fieldtype": "Date"}),
			),
			title=_("Penyusutan Ganda"),
		)


def _asset_di_jurnal(doc):
	"""Asset yang dirujuk baris-baris jurnal ini, tanpa duplikat."""
	asset = []

	for row in doc.get("accounts") or []:
		if row.reference_type == "Asset" and row.reference_name:
			if row.reference_name not in asset:
				asset.append(row.reference_name)

	return asset


def _jumlah_finance_book(asset):
	"""Berapa jurnal penyusutan yang wajar untuk satu tanggal.

	Asset dengan beberapa finance book memang menyusut beberapa kali di tanggal
	yang sama, satu per buku, jadi batasnya ikut jumlah bukunya.
	"""
	jumlah = frappe.db.count("Asset Finance Book", {"parent": asset, "parenttype": "Asset"})

	return cint(jumlah) or 1


def _jumlah_penyusutan_aktif(asset, posting_date, kecuali):
	"""Jurnal penyusutan aktif milik sebuah asset pada satu tanggal.

	Yang dihitung dokumennya, bukan barisnya: satu jurnal penyusutan menyebut
	asetnya di lebih dari satu baris.
	"""
	return cint(frappe.db.sql("""
		SELECT COUNT(DISTINCT je.name)
		FROM `tabJournal Entry` je
		JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
		WHERE je.voucher_type = %(voucher_type)s
		  AND je.posting_date = %(posting_date)s
		  AND je.docstatus = 1
		  AND je.name != %(kecuali)s
		  AND jea.reference_type = 'Asset'
		  AND jea.reference_name = %(asset)s
	""", {
		"voucher_type": VOUCHER_PENYUSUTAN,
		"posting_date": posting_date,
		"kecuali": kecuali or "",
		"asset": asset,
	})[0][0])
