import contextlib
import io

import frappe
from frappe.utils import cint, flt

from sth.accounting_sth.doctype.costing_bengkel.costing_bengkel import (
	_compute_alokasi_gaji_opr_per_kendaraan,
	build_and_submit_costing_bengkel,
	get_closing_vra_bengkel,
	get_pengeluaran_barang_bengkel,
	get_pengeluaran_barang_solar_bengkel,
	get_total_kmhm_bengkel,
)

# Selisih di bawah ini dianggap sama, supaya pembulatan float tidak dilaporkan
# sebagai perbedaan.
TOLERANSI = 0.005


def execute(terapkan=0, company=None, unit=None, dari=None, sampai=None, nama=None):
	"""Bangun ulang Costing Bengkel yang isinya berbeda dengan hitungan sekarang.

	Dua sebab yang sudah diketahui:
	- Sampai 45923431 penarik PB mencocokkan Sub Unit 'BENGKEL'/'TRAKSI' persis,
	  padahal Divisi bernama per unit (TRAKSI-TPRE), dan tabel Solar cuma menarik
	  barang 50101001. Costing Bengkel yang sudah disubmit jadi tidak memuat PB
	  kendaraan sama sekali, begitu juga Cost Per KM/HM dan jurnal Closing VRA-nya.
	- sth.patches.perbaiki_kmhm_bkm mengganti KM/HM BKM Traksi yang awalnya 0 dan
	  KM/HM BKM Bengkel yang awal/akhirnya tidak cocok. Selisih KM/HM itu dipakai
	  untuk Total Cost Per KM/HM, Alokasi Gaji Operator VRA, dan Kegiatan BKM
	  Traksi, yang semuanya berujung di Closing VRA. Jalankan patch ini sesudah
	  perbaiki_kmhm_bkm diterapkan.

	Bawaannya cuma melaporkan Costing Bengkel yang total Pengeluaran Barang atau
	Solar-nya, Alokasi Gaji Operator VRA per kendaraan, atau Closing VRA per
	akun + kendaraan-nya berbeda dengan hitungan sekarang. Yang mau dibangun
	ulang:

	    bench --site <site> execute sth.patches.bangun_ulang_costing_bengkel.execute
	    bench --site <site> execute sth.patches.bangun_ulang_costing_bengkel.execute \\
	        --kwargs "{'terapkan': 1, 'nama': 'CB-2026-0005'}"

	Penyaringnya: company, unit, dari, sampai (periode costing), atau nama satu
	dokumen. Dokumen yang sudah sama dengan hitungan sekarang dilewati, jadi
	patch ini aman diulang.

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
		selisih = bandingkan(cb)
		if not selisih:
			sama.append(cb.name)
			continue

		beda.append(cb.name)
		print("{0}  {1} {2} {3} s/d {4}".format(
			cb.name, cb.company, cb.unit or "-", cb.periode_dari, cb.periode_sampai
		))
		for baris in selisih:
			print("    " + baris)

		if not terapkan:
			print()
			continue

		titik = "bangun_ulang_costing_bengkel"
		try:
			frappe.db.savepoint(titik)
			with diam():
				baru = bangun_ulang(cb)
			print("    di-cancel, diganti {0}\n".format(baru))
		except Exception as e:
			if frappe.message_log:
				frappe.message_log.pop()

			frappe.db.rollback(save_point=titik)
			pesan = sebab(e)
			gagal.append((cb.name, pesan))
			print("    GAGAL — {0}\n".format(pesan))

	print("\nsama dengan hitungan sekarang : {0}".format(len(sama)))
	print("berbeda                       : {0}".format(len(beda)))
	print("gagal                         : {0}".format(len(gagal)))

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


def bandingkan(cb):
	"""Baris laporan perbedaan isi dokumen dengan hitungan sekarang; kosong kalau sama.

	Alokasi Gaji Operator VRA dan Closing VRA dibandingkan per kendaraan / per
	akun, bukan totalnya: gaji operator selalu habis dibagi, jadi KM/HM yang
	salah cuma menggeser porsinya antar kendaraan tanpa mengubah total.
	"""
	args = (cb.periode_dari, cb.periode_sampai, cb.company, cb.unit)

	with diam():
		pb = sum(flt(r["amount"]) for r in get_pengeluaran_barang_bengkel(*args))
		solar = sum(flt(r["amount"]) for r in get_pengeluaran_barang_solar_bengkel(*args))
		alokasi_baru = _compute_alokasi_gaji_opr_per_kendaraan(*args)
		closing_baru = jumlah_per_akun(get_closing_vra_bengkel(*args))
		kmhm = get_total_kmhm_bengkel(*args)

	hasil = []
	if abs(flt(cb.total_pengeluaran_barang) - pb) > TOLERANSI:
		hasil.append("Pengeluaran Barang  {0:>18,.2f} -> {1:>18,.2f}".format(flt(cb.total_pengeluaran_barang), pb))
	if abs(flt(cb.total_pengeluaran_barang_solar) - solar) > TOLERANSI:
		hasil.append("PB Solar/Kendaraan  {0:>18,.2f} -> {1:>18,.2f}".format(flt(cb.total_pengeluaran_barang_solar), solar))

	alokasi_lama = {}
	for r in frappe.get_all(
		"Costing Bengkel Alokasi Gaji Operator VRA",
		filters={"parent": cb.name, "parenttype": "Costing Bengkel"},
		fields=["kode_vra", "amount"],
	):
		alokasi_lama[r.kode_vra] = alokasi_lama.get(r.kode_vra, 0) + flt(r.amount)

	for kend in sorted(set(alokasi_lama) | set(alokasi_baru), key=lambda k: k or ""):
		lama, baru = flt(alokasi_lama.get(kend)), flt(alokasi_baru.get(kend))
		if abs(lama - baru) > TOLERANSI:
			hasil.append("Alokasi Gaji OPR {0:12} {1:>18,.2f} -> {2:>18,.2f}  (KM/HM periode {3:,.2f})".format(
				kend or "-", lama, baru, flt(kmhm.get(kend))))

	closing_lama = jumlah_per_akun(frappe.get_all(
		"Costing Bengkel Closing VRA",
		filters={"parent": cb.name, "parenttype": "Costing Bengkel"},
		fields=["no_coa", "kode_vra", "debit", "credit"],
	))

	for kunci in sorted(set(closing_lama) | set(closing_baru), key=lambda k: (k[1] or "", k[0] or "")):
		lama, baru = closing_lama.get(kunci, 0), closing_baru.get(kunci, 0)
		if abs(lama - baru) > TOLERANSI:
			hasil.append("Closing VRA {0:12} {1:30} {2:>18,.2f} -> {3:>18,.2f}".format(
				kunci[1] or "-", kunci[0] or "-", lama, baru))

	return hasil


def jumlah_per_akun(rows):
	"""Saldo debit - credit per (akun, kendaraan)."""
	hasil = {}
	for r in rows:
		kunci = (r.get("no_coa"), r.get("kode_vra"))
		hasil[kunci] = hasil.get(kunci, 0) + flt(r.get("debit")) - flt(r.get("credit"))
	return hasil


@contextlib.contextmanager
def diam():
	"""Redam print debug get_kegiatan_bkm_traksi_bengkel supaya laporan terbaca."""
	with contextlib.redirect_stdout(io.StringIO()):
		yield


def bangun_ulang(cb):
	frappe.get_doc("Costing Bengkel", cb.name).cancel()
	return build_and_submit_costing_bengkel(cb.company, cb.unit, cb.periode_dari, cb.periode_sampai)


def sebab(e):
	"""Pesan penolakan yang terbaca, tanpa markup frappe.throw."""
	return frappe.utils.strip_html(str(e)).strip() or e.__class__.__name__
