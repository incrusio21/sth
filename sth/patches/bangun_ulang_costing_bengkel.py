import frappe
from frappe.utils import cint, flt

from sth.accounting_sth.doctype.costing_bengkel.costing_bengkel import (
	build_and_submit_costing_bengkel,
	get_pengeluaran_barang_bengkel,
	get_pengeluaran_barang_solar_bengkel,
)

# Selisih di bawah ini dianggap sama, supaya pembulatan float tidak dilaporkan
# sebagai perbedaan.
TOLERANSI = 0.005


def execute(terapkan=0, company=None, unit=None, dari=None, sampai=None, nama=None):
	"""Bangun ulang Costing Bengkel yang Pengeluaran Barang-nya terlewat.

	Sampai 45923431 penarik PB mencocokkan Sub Unit 'BENGKEL'/'TRAKSI' persis,
	padahal Divisi bernama per unit (TRAKSI-TPRE), dan tabel Solar cuma menarik
	barang 50101001. Costing Bengkel yang sudah disubmit jadi tidak memuat PB
	kendaraan sama sekali, begitu juga Cost Per KM/HM dan jurnal Closing VRA-nya.

	Bawaannya cuma melaporkan Costing Bengkel yang total Pengeluaran Barang atau
	Solar-nya berbeda dengan tarikan sekarang. Yang mau dibangun ulang:

	    bench --site <site> execute sth.patches.bangun_ulang_costing_bengkel.execute
	    bench --site <site> execute sth.patches.bangun_ulang_costing_bengkel.execute \\
	        --kwargs "{'terapkan': 1, 'nama': 'CB-2026-0005'}"

	Penyaringnya: company, unit, dari, sampai (periode costing), atau nama satu
	dokumen. Dokumen yang sudah sama dengan tarikan sekarang dilewati, jadi patch
	ini aman diulang.

	Waktu diterapkan, dokumen lama di-cancel (GL-nya dibalik) lalu dibuat
	dokumen baru dengan company/unit/periode yang sama lewat builder yang
	dipakai Accounting Period. Yang tertolak, misalnya karena periodenya sudah
	ditutup, dilaporkan gagal dan sisanya tetap jalan.

	Sengaja tidak didaftarkan di patches.txt: membalik dan memposting ulang
	jurnal costing bukan sesuatu yang boleh jalan sendiri tiap migrate.
	"""
	terapkan = cint(terapkan)
	dokumen = cari_costing_bengkel(company=company, unit=unit, dari=dari, sampai=sampai, nama=nama)

	if not dokumen:
		print("Tidak ada Costing Bengkel submitted yang cocok dengan penyaringnya.")
		return

	print("{0} Costing Bengkel diperiksa, mode {1}\n".format(
		len(dokumen), "TERAPKAN" if terapkan else "LAPORAN SAJA"
	))

	sama = []
	beda = []
	gagal = []

	for cb in dokumen:
		args = (cb.periode_dari, cb.periode_sampai, cb.company, cb.unit)
		pb = sum(flt(r["amount"]) for r in get_pengeluaran_barang_bengkel(*args))
		solar = sum(flt(r["amount"]) for r in get_pengeluaran_barang_solar_bengkel(*args))

		if (
			abs(flt(cb.total_pengeluaran_barang) - pb) <= TOLERANSI
			and abs(flt(cb.total_pengeluaran_barang_solar) - solar) <= TOLERANSI
		):
			sama.append(cb.name)
			continue

		beda.append(cb.name)
		print("{0}  {1} {2} {3} s/d {4}".format(
			cb.name, cb.company, cb.unit or "-", cb.periode_dari, cb.periode_sampai
		))
		print("    Pengeluaran Barang  {0:>18,.2f} -> {1:>18,.2f}".format(flt(cb.total_pengeluaran_barang), pb))
		print("    PB Solar/Kendaraan  {0:>18,.2f} -> {1:>18,.2f}".format(flt(cb.total_pengeluaran_barang_solar), solar))

		if not terapkan:
			continue

		titik = "bangun_ulang_costing_bengkel"
		try:
			frappe.db.savepoint(titik)
			baru = bangun_ulang(cb)
			print("    di-cancel, diganti {0}\n".format(baru))
		except Exception as e:
			if frappe.message_log:
				frappe.message_log.pop()

			frappe.db.rollback(save_point=titik)
			pesan = sebab(e)
			gagal.append((cb.name, pesan))
			print("    GAGAL — {0}\n".format(pesan))

	print("\nsama dengan tarikan sekarang : {0}".format(len(sama)))
	print("berbeda                      : {0}".format(len(beda)))
	print("gagal                        : {0}".format(len(gagal)))

	for nama_cb, pesan in gagal:
		print("  {0}: {1}".format(nama_cb, pesan[:200]))

	if terapkan:
		frappe.db.commit()
	elif beda:
		print(
			"\nBelum ada yang disentuh. Ulangi dengan terapkan=1 untuk membangun "
			"ulang dokumen yang berbeda di atas."
		)


def cari_costing_bengkel(company=None, unit=None, dari=None, sampai=None, nama=None):
	filters = {"docstatus": 1}

	if nama:
		filters["name"] = nama
	if company:
		filters["company"] = company
	if unit:
		filters["unit"] = unit
	if dari:
		filters["periode_dari"] = (">=", dari)
	if sampai:
		filters["periode_sampai"] = ("<=", sampai)

	return frappe.get_all(
		"Costing Bengkel",
		filters=filters,
		fields=[
			"name", "company", "unit", "periode_dari", "periode_sampai",
			"total_pengeluaran_barang", "total_pengeluaran_barang_solar",
		],
		order_by="periode_dari, name",
		limit_page_length=0,
	)


def bangun_ulang(cb):
	frappe.get_doc("Costing Bengkel", cb.name).cancel()
	return build_and_submit_costing_bengkel(cb.company, cb.unit, cb.periode_dari, cb.periode_sampai)


def sebab(e):
	"""Pesan penolakan yang terbaca, tanpa markup frappe.throw."""
	return frappe.utils.strip_html(str(e)).strip() or e.__class__.__name__
