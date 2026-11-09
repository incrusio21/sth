import frappe
from erpnext.accounts.general_ledger import make_reverse_gl_entries
from erpnext.stock.doctype.repost_item_valuation.repost_item_valuation import repost_entries
from frappe.utils import cint, flt, getdate

from sth.overrides.purchase_receipt import make_gl_entries_for_non_stock_items

DOCTYPE = "Purchase Receipt"


def execute(terapkan=0, nama=None, company=None, dari=None, sampai=None):
	"""Posting ulang Purchase Receipt submitted yang masuk ke gudang Material Request.

	PO hasil Supplier Quotation dulu barisnya masih membawa gudang Material Request,
	sedangkan Set Target Warehouse-nya gudang central. Purchase Receipt mengambil
	gudang dari baris PO, jadi barang tercatat masuk gudang yang salah. Patch ini
	memindahkan baris PREC ke Set Target Warehouse PO-nya dan memposting ulang
	stok dan jurnalnya di tanggal aslinya:

	    1. SLE dan GL lama dibalik, sama seperti cancel.
	    2. warehouse baris PREC diganti ke set_warehouse PO.
	    3. SLE dan GL baru diposting, lalu Repost Item Valuation dijalankan supaya
	       transaksi sesudahnya di kedua gudang ikut dihitung ulang.

	Yang dilewati (dicetak alasannya, diselesaikan manual):

	    - PREC yang tanggalnya masuk Accounting Period yang menutup Purchase
	      Receipt, tanggal beku akun, atau Period Closing Voucher
	    - PREC yang sudah punya retur (Purchase Return) submitted
	    - PREC yang punya barang serial/batch atau barang aset
	    - PREC yang stoknya di gudang lama sudah terpakai: memindahkan
	      penerimaannya membuat gudang lama minus sesudah tanggal itu. Stok
	      seperti ini lebih tepat dipindah dengan Stock Entry Material Transfer.

	Jalankan patch samakan_gudang_baris_po dulu supaya baris PO-nya sudah benar.
	Pengecekan stok di uji coba dihitung per PREC sendiri-sendiri; kalau ada
	beberapa PREC untuk barang dan gudang yang sama, hasil terapkan bisa
	melewati sebagian yang di uji coba terlihat lolos.

	Tidak didaftarkan di patches.txt. Default-nya uji coba:

	    bench --site <site> execute sth.patches.pindah_gudang_prec_po.execute
	    bench --site <site> execute sth.patches.pindah_gudang_prec_po.execute \\
	        --kwargs "{'terapkan': 1}"
	    bench --site <site> execute sth.patches.pindah_gudang_prec_po.execute \\
	        --kwargs "{'terapkan': 1, 'nama': 'MAT-PRE-2026-00001'}"

	Aman diulang: baris yang gudangnya sudah sama dengan set_warehouse PO tidak
	ikut dicari lagi.
	"""
	terapkan = cint(terapkan)
	print("Mode {0}\n".format("TERAPKAN" if terapkan else "LAPORAN SAJA"))

	rencana = cari_baris(nama, company, dari, sampai)
	if not rencana:
		print("Tidak ada Purchase Receipt yang perlu dipindah gudangnya.")
		return

	berhasil, dilewati = [], []

	for pr, rows in rencana.items():
		for row in rows:
			print("{0} #{1} {2} ({3}): {4} -> {5}".format(
				pr, row.idx, row.item_code, flt(row.stock_qty), row.warehouse, row.gudang_baru
			))

		alasan = alasan_dilewati(pr, rows)
		if alasan:
			print("    DILEWATI: {0}".format(alasan))
			dilewati.append((pr, alasan))
			continue

		if not terapkan:
			berhasil.append(pr)
			continue

		try:
			posting_ulang(pr, rows)
			repost_entries()
			frappe.db.commit()
			berhasil.append(pr)
			print("    selesai diposting ulang")
		except Exception:
			frappe.db.rollback()
			alasan = frappe.get_traceback().strip().splitlines()[-1]
			print("    GAGAL: {0}".format(alasan))
			dilewati.append((pr, alasan))

	print("\n{0} PREC {1}, {2} dilewati.".format(
		len(berhasil), "diposting ulang" if terapkan else "akan diposting ulang", len(dilewati)
	))


def cari_baris(nama=None, company=None, dari=None, sampai=None):
	"""Baris PREC submitted dari PO hasil Supplier Quotation yang gudangnya bukan set_warehouse PO."""
	syarat, nilai = [], {}

	if nama:
		syarat.append("pr.name = %(nama)s")
		nilai["nama"] = nama
	if company:
		syarat.append("pr.company = %(company)s")
		nilai["company"] = company
	if dari:
		syarat.append("pr.posting_date >= %(dari)s")
		nilai["dari"] = dari
	if sampai:
		syarat.append("pr.posting_date <= %(sampai)s")
		nilai["sampai"] = sampai

	rows = frappe.db.sql(
		"""
		SELECT pr.name AS pr, pri.name, pri.idx, pri.item_code, pri.warehouse,
			pri.stock_qty, po.set_warehouse AS gudang_baru
		FROM `tabPurchase Receipt Item` pri
		JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
		JOIN `tabPurchase Order Item` poi ON poi.name = pri.purchase_order_item
		JOIN `tabPurchase Order` po ON po.name = poi.parent
		WHERE pr.docstatus = 1 AND pr.is_return = 0
			AND IFNULL(po.set_warehouse, '') != ''
			AND IFNULL(poi.supplier_quotation, '') != ''
			AND IFNULL(pri.warehouse, '') != ''
			AND pri.warehouse != po.set_warehouse
			{0}
		ORDER BY pr.posting_date, pr.posting_time, pr.name, pri.idx
		""".format("".join(" AND " + s for s in syarat)),
		nilai,
		as_dict=1,
	)

	rencana = {}
	for row in rows:
		rencana.setdefault(row.pr, []).append(row)

	return rencana


def alasan_dilewati(pr, rows):
	doc = frappe.db.get_value(
		DOCTYPE, pr, ["company", "posting_date", "posting_time"], as_dict=True
	)

	alasan = alasan_periode(doc.company, doc.posting_date)
	if alasan:
		return alasan

	retur = frappe.db.get_value(DOCTYPE, {"return_against": pr, "docstatus": 1}, "name")
	if retur:
		return "sudah ada retur {0}".format(retur)

	khusus = frappe.db.sql(
		"""
		SELECT pri.item_code
		FROM `tabPurchase Receipt Item` pri
		JOIN `tabItem` i ON i.name = pri.item_code
		WHERE pri.parent = %s
			AND (IFNULL(pri.serial_and_batch_bundle, '') != ''
				OR IFNULL(pri.serial_no, '') != '' OR IFNULL(pri.batch_no, '') != ''
				OR i.is_fixed_asset = 1)
		LIMIT 1
		""",
		pr,
	)
	if khusus:
		return "barang {0} serial/batch atau aset".format(khusus[0][0])

	# Penerimaan yang dipindah keluar dari gudang lama mengurangi saldo gudang itu
	# di setiap transaksi sesudahnya, jadi saldo terendah sejak tanggal PREC harus
	# masih cukup.
	keluar = {}
	for row in rows:
		kunci = (row.item_code, row.warehouse)
		keluar[kunci] = flt(keluar.get(kunci)) + flt(row.stock_qty)

	for (item_code, gudang), qty in keluar.items():
		terendah = frappe.db.sql(
			"""
			SELECT MIN(qty_after_transaction)
			FROM `tabStock Ledger Entry`
			WHERE item_code = %(item)s AND warehouse = %(gudang)s AND is_cancelled = 0
				AND TIMESTAMP(posting_date, posting_time) >= TIMESTAMP(%(tanggal)s, %(jam)s)
			""",
			{"item": item_code, "gudang": gudang, "tanggal": doc.posting_date, "jam": doc.posting_time},
		)[0][0]

		if flt(terendah) - qty < 0:
			return "stok {0} di {1} sudah terpakai (saldo terendah {2}, dipindah {3})".format(
				item_code, gudang, flt(terendah), qty
			)


def alasan_periode(company, posting_date):
	"""Penjaga periode yang biasanya diperiksa saat posting Purchase Receipt."""
	periode = frappe.db.sql(
		"""
		SELECT ap.name
		FROM `tabAccounting Period` ap
		JOIN `tabClosed Document` cd ON cd.parent = ap.name
		WHERE ap.company = %(company)s AND cd.closed = 1
			AND cd.document_type = 'Purchase Receipt'
			AND %(tanggal)s BETWEEN ap.start_date AND ap.end_date
		LIMIT 1
		""",
		{"company": company, "tanggal": posting_date},
	)
	if periode:
		return "periode ditutup Accounting Period {0}".format(periode[0][0])

	beku = frappe.db.get_single_value("Accounts Settings", "acc_frozen_upto")
	if beku and getdate(posting_date) <= getdate(beku):
		return "akun dibekukan sampai {0}".format(beku)

	pcv = frappe.db.get_value(
		"Period Closing Voucher",
		{"docstatus": 1, "company": company, "period_end_date": (">=", posting_date)},
		"name",
	)
	if pcv:
		return "sudah ada Period Closing Voucher {0}".format(pcv)


def posting_ulang(pr, rows):
	# 1. Balik SLE dan GL lama dengan jalur cancel bawaan, selagi baris masih
	#    menunjuk gudang lama, supaya Bin gudang lama ikut berkurang.
	lama = frappe.get_doc(DOCTYPE, pr)
	lama.docstatus = 2
	lama.update_stock_ledger()
	make_reverse_gl_entries(voucher_type=DOCTYPE, voucher_no=pr)

	# 2. Pindahkan gudang baris.
	for row in rows:
		frappe.db.set_value(
			"Purchase Receipt Item", row.name, "warehouse", row.gudang_baru, update_modified=False
		)

	# 3. Posting ulang di tanggal aslinya, lalu antrekan repost untuk transaksi
	#    sesudahnya di gudang lama dan gudang baru.
	baru = frappe.get_doc(DOCTYPE, pr)
	baru.update_stock_ledger()
	baru.make_gl_entries()
	# GL barang non-stok diposting terpisah oleh SthPurchaseReceipt.on_submit dan
	# ikut terbalik di langkah 1, jadi diposting lagi.
	make_gl_entries_for_non_stock_items(baru)

	# Repost per barang dan gudang ikut memposting ulang GL transaksi sesudahnya.
	for row in rows:
		for gudang in (row.warehouse, row.gudang_baru):
			riv = frappe.new_doc("Repost Item Valuation")
			riv.update({
				"based_on": "Item and Warehouse",
				"item_code": row.item_code,
				"warehouse": gudang,
				"posting_date": baru.posting_date,
				"posting_time": baru.posting_time,
				"company": baru.company,
			})
			riv.flags.ignore_links = True
			riv.flags.ignore_permissions = True
			riv.submit()
