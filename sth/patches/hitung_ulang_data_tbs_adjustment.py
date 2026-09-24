import frappe
from frappe.utils import flt

from sth.mill.doctype.data_tbs.data_tbs import (
	DOCTYPE,
	angka_turunan,
	hitung_ulang_rantai,
	ste_sudah_benar,
)

# Nama field angka_turunan, urutannya sama, untuk mencetak apa yang bergeser.
FIELDS = (
	"jumlah_tbs_diterima", "jumlah_tbs_restan", "adjustment_stok", "restan_setelah_adjustment",
	"grand_total_tbs",
	"berat_rata_rata_tbs", "tbs_olah", "tbs_restan", "tbs_loading_ramp", "total_tbs_restan",
)


def execute(units=None, simpan=True):
	"""Hitung ulang Data TBS sesudah Stock Entry manual yang sudah telanjur disubmit.

	Adjustment stok Data TBS baru dibaca sejak kodenya ada, dan pemicunya cuma
	jalan waktu Stock Entry disubmit atau dibatalkan — Stock Entry manual yang
	disubmit sebelumnya, mis. MAT-STE-2026-02719, tidak pernah memicunya. Patch
	ini mencari Stock Entry manual paling awal di gudang TBS tiap unit, lalu
	menjalankan hitung_ulang_rantai sejak tanggal itu, persis seperti yang akan
	diantrikan pemicunya.

	Yang dicari sama dengan get_adjustment_tbs: Stock Ledger Entry di gudang
	TBS yang bukan Stock Entry buatan Data TBS dan bukan Stock Reconciliation.

	Hitung ulangnya juga membaca ulang TBS diterima dari Timbangan dan memposting
	ulang Stock Entry harian yang qty-nya berubah. TBS olah yang bergeser tidak
	menyusul ke sounding; OER/KER hari itu perlu Hitung Ulang sounding terpisah.

	Tidak didaftarkan di patches.txt. Uji coba dulu — angka dokumennya dihitung
	lalu di-rollback, Stock Entry tidak disentuh:

	    bench --site <site> execute sth.patches.hitung_ulang_data_tbs_adjustment.execute --kwargs "{'simpan': False}"

	Lalu jalankan, untuk semua unit atau sebagian:

	    bench --site <site> execute sth.patches.hitung_ulang_data_tbs_adjustment.execute
	    bench --site <site> execute sth.patches.hitung_ulang_data_tbs_adjustment.execute --kwargs "{'units': ['TPRM']}"
	"""
	if isinstance(units, str):
		units = [u.strip() for u in units.split(",") if u.strip()]

	rencana = _stock_entry_manual_pertama(units)

	if not rencana:
		print("Hitung ulang Data TBS: tidak ada Stock Entry manual di gudang TBS yang menyentuh Data TBS")
		return

	for unit, sejak, voucher in rencana:
		print(f"Data TBS {unit} sejak {sejak} (Stock Entry manual pertama: {voucher})")

		if simpan:
			hasil = hitung_ulang_rantai(unit, sejak, lapor=lambda pesan: print(f"  {pesan}"))
			print(f"  {hasil.dokumen} dokumen, {hasil.angka} angka berubah, {hasil.ste} Stock Entry dibuat ulang")
			if hasil.kembar:
				print(f"  Dilewati karena kembar di tanggal yang sama: {', '.join(hasil.kembar)}")
		else:
			_uji_coba(unit, sejak)


def _stock_entry_manual_pertama(units=None):
	"""[(unit, tanggal, voucher)] Stock Entry manual paling awal per unit yang punya Data TBS sesudahnya."""
	baris = frappe.db.sql("""
		select w.unit, sle.posting_date, sle.voucher_no
		from `tabStock Ledger Entry` sle
		join `tabWarehouse` w on w.name = sle.warehouse and w.warehouse_category = 'TBS'
		join `tabItem` i on i.name = sle.item_code and i.tipe_barang = 'TBS'
		left join `tabStock Entry` se
			on se.name = sle.voucher_no and sle.voucher_type = 'Stock Entry'
		where sle.is_cancelled = 0
			and sle.voucher_type != 'Stock Reconciliation'
			and ifnull(se.reference_doctype, '') != %(doctype)s
			and ifnull(w.unit, '') != ''
		order by sle.posting_date, sle.posting_time
	""", {"doctype": DOCTYPE}, as_dict=True)

	rencana = {}
	for b in baris:
		if units and b.unit not in units:
			continue
		rencana.setdefault(b.unit, (b.unit, b.posting_date, b.voucher_no))

	return [
		r for r in rencana.values()
		if frappe.db.exists(DOCTYPE, {"unit": r[0], "docstatus": ("<", 2), "tanggal_produksi": (">=", r[1])})
	]


def _uji_coba(unit, sejak):
	"""Hitung angka dokumennya tanpa Stock Entry, cetak yang bergeser, lalu rollback."""
	dokumen = frappe.get_all(
		DOCTYPE,
		filters={"unit": unit, "docstatus": ("<", 2), "tanggal_produksi": (">=", sejak)},
		fields=["name", "tanggal_produksi"],
		order_by="tanggal_produksi asc, creation asc",
		limit_page_length=0,
	)
	sebelum = {d.name: angka_turunan(frappe.get_doc(DOCTYPE, d.name)) for d in dokumen}

	try:
		hitung_ulang_rantai(unit, sejak, posting_ulang=False, commit=False)

		ste_berubah = 0
		for d in dokumen:
			doc = frappe.get_doc(DOCTYPE, d.name)
			sesudah = angka_turunan(doc)
			perlu_ste = doc.docstatus == 1 and not ste_sudah_benar(doc)
			ste_berubah += perlu_ste

			if sesudah == sebelum[d.name] and not perlu_ste:
				continue

			beda = ", ".join(
				f"{field} {flt(lama):,.3f} -> {flt(baru):,.3f}"
				for field, lama, baru in zip(FIELDS, sebelum[d.name], sesudah)
				if lama != baru
			)
			print(f"  {d.name} {d.tanggal_produksi}: {beda or 'angka sama'}{' | STE diposting ulang' if perlu_ste else ''}")

		print(f"  (uji coba) {len(dokumen)} dokumen, {ste_berubah} Stock Entry akan diposting ulang")
	finally:
		frappe.db.rollback()
