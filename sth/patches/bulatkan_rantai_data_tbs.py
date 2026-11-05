import frappe
from erpnext.stock.doctype.repost_item_valuation.repost_item_valuation import repost_entries
from erpnext.stock.utils import get_stock_balance
from frappe.utils import flt, getdate

from sth.mill.doctype.data_tbs.data_tbs import (
	DOCTYPE,
	get_warehouse_tbs,
	hitung_ulang_rantai,
	ste_sudah_benar,
)

# hitung_ulang_rantai dibaca ulang sampai tidak ada lagi yang bergeser. Dua
# putaran sudah cukup untuk kasus DTBS-0189; batasnya cuma pengaman.
PUTARAN_MAKS = 4


def execute(units=None, terapkan=False, dari="2026-10-01", sampai="2026-10-31"):
	"""Posting ulang Stock Entry Data TBS yang meleset 0,01 kg karena pembulatan.

	Dulu pergerakan_stok membulatkan selisih restan sesudah dikurangkan,
	padahal rantai restannya menyimpan angka tanpa pembulatan. Selisih yang
	dibulatkan belakangan tidak menjumlah pas, jadi saldo gudang TBS meleset
	0,01 kg sesekali, dan hari yang TBS-nya habis diolah gagal disubmit karena
	stoknya kurang 0,01 — kasus DTBS-0189 (ASRM, 31 Oktober 2026).

	Patch ini mencari Data TBS submitted paling awal per unit yang STE-nya tidak
	cocok lagi dengan pergerakan_stok yang baru, lalu menjalankan
	hitung_ulang_rantai sejak tanggal itu. Putarannya diulang: dokumen yang
	restan awalnya diambil dari saldo gudang (sesudah restan nol) baru membaca
	saldo yang benar sesudah STE sebelumnya diposting ulang dan Repost Item
	Valuation-nya selesai. Karena itu antrean Repost Item Valuation dijalankan
	di antara putaran — semua yang mengantre, bukan cuma milik patch ini.

	Yang dicari cuma STE meleset di [dari, sampai] — default-nya Oktober 2026.
	Rantainya tetap dihitung ulang sampai dokumen terakhir, karena restan
	Oktober menjadi restan awal November; STE sesudah `sampai` cuma diposting
	ulang kalau ikut bergeser karenanya.

	STE lama dibatalkan dan dibuat ulang di tanggal aslinya, jadi yang
	dikerjakan cuma dokumen sesudah Accounting Period terakhir unit itu yang
	menutup Stock Entry. STE meleset sebelum batas itu dilewati — termasuk yang
	periodenya masih terbuka, karena Repost Item Valuation-nya ikut menggeser
	nilai di periode yang sudah tutup. Selisih dari masa itu tetap terbawa;
	saldo akhir tiap unit dicetak supaya kelihatan, dan kalau perlu dipotong
	dengan Restan Awal TBS sebesar saldo gudang di awal periode terbuka.

	Tidak didaftarkan di patches.txt. Default-nya uji coba — cuma mencetak unit,
	tanggal mulai, dan jumlah STE yang meleset:

	    bench --site <site> execute sth.patches.bulatkan_rantai_data_tbs.execute

	Lalu jalankan, untuk semua unit atau sebagian:

	    bench --site <site> execute sth.patches.bulatkan_rantai_data_tbs.execute --kwargs "{'terapkan': 1}"
	    bench --site <site> execute sth.patches.bulatkan_rantai_data_tbs.execute --kwargs "{'terapkan': 1, 'units': ['ASRM']}"
	    bench --site <site> execute sth.patches.bulatkan_rantai_data_tbs.execute --kwargs "{'terapkan': 1, 'dari': '2026-11-01', 'sampai': '2026-11-30'}"
	"""
	if isinstance(units, str):
		units = [u.strip() for u in units.split(",") if u.strip()]

	dari, sampai = getdate(dari), getdate(sampai)
	rencana = _ste_meleset(units, dari, sampai)

	if not rencana:
		print(f"Stock Entry Data TBS {dari} s/d {sampai} sudah sesuai semua.")
		return

	dikerjakan = {}
	for unit, daftar in rencana.items():
		batas = _batas_periode_tutup(unit)
		terbuka = [d for d in daftar if not batas or getdate(d[0]) > batas]
		dilewati = len(daftar) - len(terbuka)

		keterangan = f", {dilewati} dilewati karena sebelum periode tutup {batas}" if dilewati else ""
		if terbuka:
			print(f"{unit}: {len(terbuka)} STE meleset, sejak {terbuka[0][0]} ({terbuka[0][1]}){keterangan}")
			dikerjakan[unit] = terbuka[0][0]
		else:
			print(f"{unit}: tidak ada STE meleset di periode terbuka{keterangan}")

	if not terapkan:
		print("(uji coba) Tidak ada yang diubah. Jalankan dengan --kwargs \"{'terapkan': 1}\" untuk memposting ulang.")
		return

	for unit, sejak in dikerjakan.items():
		try:
			for putaran in range(1, PUTARAN_MAKS + 1):
				hasil = hitung_ulang_rantai(unit, sejak)
				repost_entries()
				frappe.db.commit()

				print(f"{unit} putaran {putaran}: {hasil.angka} angka berubah, {hasil.ste} STE diposting ulang")
				if hasil.kembar:
					print(f"  Dilewati karena kembar di tanggal yang sama: {', '.join(hasil.kembar)}")

				if not (hasil.angka or hasil.ste):
					break
			else:
				print(f"{unit}: masih bergeser sesudah {PUTARAN_MAKS} putaran, periksa manual.")
		except Exception:
			frappe.db.rollback()
			print(f"{unit} GAGAL: {frappe.get_traceback().strip().splitlines()[-1]}")

		_cek_saldo(unit)


def _batas_periode_tutup(unit):
	"""Tanggal akhir Accounting Period terakhir unit ini yang menutup Stock Entry, atau None.

	Syaratnya sama dengan validate_accounting_period_on_doc_save di
	sth.overrides.accounting_period.
	"""
	batas = frappe.db.sql("""
		select max(ap.end_date)
		from `tabAccounting Period` ap
		join `tabClosed Document` cd on cd.parent = ap.name and cd.parenttype = 'Accounting Period'
		where ap.unit = %(unit)s and ap.workflow_state = 'Submitted'
			and cd.document_type = 'Stock Entry' and cd.closed = 1
	""", {"unit": unit})

	return getdate(batas[0][0]) if batas and batas[0][0] else None


def _ste_meleset(units, dari, sampai):
	"""{unit: [(tanggal, nama)]} Data TBS submitted di [dari, sampai] yang STE-nya tidak cocok, urut tanggal."""
	filters = {"docstatus": 1, "tanggal_produksi": ("between", [dari, sampai])}
	if units:
		filters["unit"] = ("in", units)

	rencana = {}
	for row in frappe.get_all(
		DOCTYPE,
		filters=filters,
		fields=["name", "unit", "tanggal_produksi"],
		order_by="tanggal_produksi asc, creation asc",
		limit_page_length=0,
	):
		if not ste_sudah_benar(frappe.get_doc(DOCTYPE, row.name)):
			rencana.setdefault(row.unit, []).append((row.tanggal_produksi, row.name))

	return rencana


def _cek_saldo(unit):
	"""Cetak saldo gudang TBS sesudah Data TBS submitted terakhir dibanding restannya.

	Stock Entry manual bertanggal sama dengan dokumen itu milik dokumen
	berikutnya, jadi kalau ada, bedanya wajar.
	"""
	terakhir = frappe.get_all(
		DOCTYPE,
		filters={"unit": unit, "docstatus": 1},
		fields=["name", "tanggal_produksi", "total_tbs_restan"],
		order_by="tanggal_produksi desc, creation desc",
		limit=1,
	)
	gudang = get_warehouse_tbs(unit)
	item = frappe.db.get_value("Item", {"tipe_barang": "TBS"})

	if not (terakhir and gudang and item):
		return

	doc = terakhir[0]
	saldo = flt(get_stock_balance(item, gudang, doc.tanggal_produksi, "23:59:59"), 2)
	restan = flt(doc.total_tbs_restan, 2)
	status = "cocok" if saldo == restan else f"BEDA {flt(saldo - restan, 2)}"

	print(f"  {doc.name} {doc.tanggal_produksi}: saldo gudang {saldo:,.2f}, restan {restan:,.2f} — {status}")
