import frappe
from frappe.utils import flt

VOUCHER_PENYUSUTAN = "Depreciation Entry"


def execute():
	"""Batalkan jurnal penyusutan yang terbukukan berulang.

	Pelepasan yang dibatalkan tidak pernah mereset depreciation schedule, jadi
	pelepasan berikutnya memposting ulang seluruh baris yang belum punya JE —
	termasuk bulan yang sudah dibukukan. Satu asset bisa mengulang pola yang sama
	sampai enam kali.

	Yang dipertahankan adalah siklus terakhir, karena itulah yang cocok dengan
	keadaan asetnya sekarang. Seluruh siklus sebelumnya dibatalkan.

	Sengaja TIDAK didaftarkan di patches.txt: membatalkan puluhan jurnal diam-diam
	waktu migrate terlalu berisiko. Jalankan sendiri, dan periksa angkanya dulu —
	dry_run tidak mengubah apa pun:

	    bench --site <site> execute sth.patches.batalkan_penyusutan_ganda.dry_run
	    bench --site <site> execute sth.patches.batalkan_penyusutan_ganda.execute
	"""
	jalankan(dry=False)


@frappe.whitelist()
def dry_run():
	"""Tampilkan rencana pembatalan tanpa mengubah apa pun."""
	return jalankan(dry=True)


def jalankan(dry=True):
	hasil = []

	for asset in cari_asset_bermasalah():
		rencana = susun_rencana(asset)
		if not rencana:
			continue

		hasil.append(rencana)
		tampilkan(rencana)

		if not dry:
			terapkan(rencana)

	if not hasil:
		print("Tidak ada penyusutan ganda.")

	return hasil


def cari_asset_bermasalah():
	"""Asset yang punya schedule_date terbukukan lebih dari sekali."""
	return frappe.db.sql_list("""
		SELECT ads.asset
		FROM `tabDepreciation Schedule` ds
		JOIN `tabAsset Depreciation Schedule` ads ON ads.name = ds.parent
		WHERE ads.docstatus = 1
		  AND ds.journal_entry IS NOT NULL
		  AND ds.journal_entry != ''
		GROUP BY ads.asset
		HAVING COUNT(*) > COUNT(DISTINCT ds.schedule_date)
	""")


def susun_rencana(asset):
	"""Pisahkan baris siklus terakhir dari siklus-siklus sebelumnya.

	Baris schedule tersimpan berurutan, dan tiap siklus selalu dimulai ulang dari
	tanggal paling awal. Jadi siklus terakhir adalah rangkaian di ujung yang
	dimulai dari kemunculan terakhir tanggal pertama itu.
	"""
	baris = frappe.db.sql("""
		SELECT ds.name, ds.idx, ds.schedule_date, ds.depreciation_amount, ds.journal_entry, ads.name AS schedule
		FROM `tabDepreciation Schedule` ds
		JOIN `tabAsset Depreciation Schedule` ads ON ads.name = ds.parent
		WHERE ads.docstatus = 1
		  AND ads.asset = %(asset)s
		  AND ds.journal_entry IS NOT NULL
		  AND ds.journal_entry != ''
		ORDER BY ds.idx
	""", {"asset": asset}, as_dict=True)

	if not baris:
		return None

	tanggal_awal = baris[0].schedule_date
	mulai_siklus_terakhir = 0

	for posisi, row in enumerate(baris):
		if row.schedule_date == tanggal_awal:
			mulai_siklus_terakhir = posisi

	duplikat = baris[:mulai_siklus_terakhir]
	dipertahankan = baris[mulai_siklus_terakhir:]

	if not duplikat:
		return None

	return {
		"asset": asset,
		"duplikat": duplikat,
		"dipertahankan": dipertahankan,
		"nilai_duplikat": flt(sum(flt(r.depreciation_amount) for r in duplikat), 2),
		"nilai_dipertahankan": flt(sum(flt(r.depreciation_amount) for r in dipertahankan), 2),
	}


def tampilkan(rencana):
	print("\n{0}".format(rencana["asset"]))
	print("  dibatalkan   : {0} baris, Rp {1:,.2f}".format(
		len(rencana["duplikat"]), rencana["nilai_duplikat"]
	))
	print("  dipertahankan: {0} baris, Rp {1:,.2f}".format(
		len(rencana["dipertahankan"]), rencana["nilai_dipertahankan"]
	))
	for row in rencana["duplikat"]:
		print("    batal idx {0:>3} {1} Rp {2:>14,.2f}  {3}".format(
			row.idx, row.schedule_date, flt(row.depreciation_amount), row.journal_entry
		))


def terapkan(rencana):
	"""Batalkan JE duplikat, lepas baris schedule-nya, lalu rapikan angka asset."""
	for row in rencana["duplikat"]:
		batalkan_jurnal(row.journal_entry)
		frappe.db.delete("Depreciation Schedule", {"name": row.name})

	rapikan_schedule(rencana)
	rapikan_asset(rencana)


def batalkan_jurnal(nama):
	je = frappe.get_doc("Journal Entry", nama)

	if je.docstatus != 1:
		return

	# penjaga penyusutan ganda memeriksa saat submit, bukan cancel, tapi
	# flags-nya ikut dipasang supaya jalur pembalikan tidak saling menghalangi
	frappe.flags.is_reverse_depr_entry = True
	try:
		je.flags.ignore_permissions = True
		je.cancel()
	finally:
		frappe.flags.is_reverse_depr_entry = False


def rapikan_schedule(rencana):
	"""Urutkan ulang idx dan akumulasi baris yang tersisa."""
	akumulasi = 0

	for urutan, row in enumerate(rencana["dipertahankan"], start=1):
		akumulasi = flt(akumulasi + flt(row.depreciation_amount), 2)
		frappe.db.set_value("Depreciation Schedule", row.name, {
			"idx": urutan,
			"accumulated_depreciation_amount": akumulasi,
		}, update_modified=False)


def rapikan_asset(rencana):
	"""Kembalikan jumlah penyusutan terbukukan dan nilai buku ke angka sebenarnya."""
	asset = frappe.get_doc("Asset", rencana["asset"])
	terbukukan = len(rencana["dipertahankan"])
	nilai_buku = flt(flt(asset.gross_purchase_amount) - rencana["nilai_dipertahankan"], 2)

	for row in asset.get("finance_books") or []:
		frappe.db.set_value("Asset Finance Book", row.name, {
			"total_number_of_booked_depreciations": terbukukan,
			"value_after_depreciation": nilai_buku,
		}, update_modified=False)

	print("  asset diperbarui: {0} penyusutan terbukukan, nilai buku Rp {1:,.2f}".format(
		terbukukan, nilai_buku
	))
