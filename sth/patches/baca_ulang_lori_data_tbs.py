import frappe
from frappe.utils import flt, getdate

from sth.mill.doctype.data_tbs.data_tbs import DOCTYPE, get_lori_monitoring, hitung_ulang_rantai
from sth.patches.hitung_ulang_data_tbs_adjustment import _uji_coba

LORI = ("jumlah_lori_olah", "jumlah_lori_mentah", "jumlah_lori_masak", "lori_estimasi_loading_ramp")


def execute(units=None, simpan=True):
	"""Baca ulang lori/cycle Data TBS dari Monitoring TBS Olah, lalu hitung ulang rantainya.

	Lori/Cycle Olah, Mentah, dan Masak dulu field Int dan dihitung pakai cint,
	jadi pabrik bertipe Cycle — yang mencatat cycle-nya dalam pecahan — kehilangan
	komanya: 12,5 cycle tersimpan 12, dan TBS-nya bergeser ke porsi lain. Angka
	yang terpotong itu sudah telanjur tersimpan di kolomnya, jadi tidak bisa
	dihitung ulang dari dokumennya sendiri; harus dibaca lagi dari Monitoring.

	Jalankan sesudah migrate, waktu ketiga kolomnya sudah decimal — sebelum itu
	angka yang ditulis ikut terpotong lagi.

	Cuma dokumen yang lorinya beda dengan Monitoring yang ditulis. Dokumen tanpa
	Monitoring TBS Olah dibiarkan: bisa saja hari tidak olah yang dilewati
	pengecekannya. Sesudah itu hitung_ulang_rantai dijalankan per unit sejak
	dokumen paling awal yang berubah, yang menghitung ulang TBS olah, restan,
	rantai restan hari-hari sesudahnya, dan memposting ulang Stock Entry harian
	yang qty-nya jadi tidak cocok. TBS olah yang bergeser tidak menyusul ke
	sounding; OER/KER hari itu perlu hitung_ulang_rekap_sounding terpisah.

	Tidak didaftarkan di patches.txt. Uji coba dulu — lori dan angka dokumennya
	dihitung lalu di-rollback, Stock Entry tidak disentuh:

	    bench --site <site> execute sth.patches.baca_ulang_lori_data_tbs.execute --kwargs "{'simpan': False}"

	Lalu jalankan, untuk semua unit atau sebagian:

	    bench --site <site> execute sth.patches.baca_ulang_lori_data_tbs.execute
	    bench --site <site> execute sth.patches.baca_ulang_lori_data_tbs.execute --kwargs "{'units': ['TPRM']}"
	"""
	belum_decimal = [f for f in LORI if frappe.get_meta(DOCTYPE).get_field(f).fieldtype != "Float"]
	if belum_decimal:
		frappe.throw("Jalankan bench migrate dulu: {0} masih Int.".format(", ".join(belum_decimal)))

	if isinstance(units, str):
		units = [u.strip() for u in units.split(",") if u.strip()]

	rencana = _lori_yang_beda(units)

	if not rencana:
		print("Baca ulang lori Data TBS: semua lori sudah sama dengan Monitoring TBS Olah")
		return

	for unit, perubahan in rencana.items():
		sejak = min(getdate(row.tanggal_produksi) for row, _ in perubahan)
		print(f"Data TBS {unit} sejak {sejak}: {len(perubahan)} dokumen lorinya dibaca ulang")

		for row, lori in perubahan:
			beda = ", ".join(
				f"{field} {flt(row[field]):,.2f} -> {flt(lori[field]):,.2f}"
				for field in LORI
				if flt(row[field], 3) != flt(lori[field], 3)
			)
			print(f"  {row.name} {row.tanggal_produksi}: {beda}")
			frappe.db.set_value(DOCTYPE, row.name, lori, update_modified=False)

		if simpan:
			frappe.db.commit()
			hasil = hitung_ulang_rantai(unit, sejak, lapor=lambda pesan: print(f"  {pesan}"))
			print(f"  {hasil.dokumen} dokumen, {hasil.angka} angka berubah, {hasil.ste} Stock Entry dibuat ulang")
			if hasil.kembar:
				print(f"  Dilewati karena kembar di tanggal yang sama: {', '.join(hasil.kembar)}")
		else:
			# Rollback di dalamnya ikut membuang lori yang baru ditulis di atas.
			_uji_coba(unit, sejak)


def _lori_yang_beda(units=None):
	"""{unit: [(dokumen, lori Monitoring)]} Data TBS yang lorinya beda dengan Monitoring TBS Olah."""
	dokumen = frappe.get_all(
		DOCTYPE,
		filters={"docstatus": ("<", 2), "unit": ("is", "set"), "tanggal_produksi": ("is", "set")},
		fields=["name", "unit", "pabrik", "tanggal_produksi", *LORI],
		order_by="unit asc, tanggal_produksi asc, creation asc",
		limit_page_length=0,
	)

	rencana = {}
	for row in dokumen:
		if units and row.unit not in units:
			continue

		lori = get_lori_monitoring(row.tanggal_produksi, row.pabrik)
		if not lori or all(flt(row[f], 3) == flt(lori[f], 3) for f in LORI):
			continue

		rencana.setdefault(row.unit, []).append((row, {f: flt(lori[f]) for f in LORI}))

	return rencana
