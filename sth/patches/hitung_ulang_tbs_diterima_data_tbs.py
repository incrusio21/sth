import frappe
from frappe.utils import flt, getdate

from sth.mill.doctype.data_tbs.data_tbs import hitung_ulang_rantai
from sth.patches import hitung_ulang_rekap_sounding

DOCTYPE = "Data TBS"
PATOKAN = "Restan Awal TBS"

# Hanya September ke atas yang dibetulkan. Dokumen sebelumnya dibiarkan apa
# adanya beserta Stock Entry-nya, jadi periode yang sudah dilaporkan tidak ikut
# bergerak.
SEJAK = "2026-09-01"

# Restan awal yang ditetapkan untuk dokumen pertama tiap unit sejak SEJAK,
# menggantikan perantaian dari dokumen terakhir sebelum tanggal itu. Angkanya
# hasil hitungan di luar sistem, bukan turunan dokumen mana pun, jadi ditulis
# di sini supaya tercatat di git — bukan diketik di konsol waktu menjalankan.
# Patch ini menuangkannya jadi Restan Awal TBS, supaya Hitung Ulang dan
# Timbangan bertanggal mundur sesudahnya tetap memakai angka yang sama.
RESTAN_AWAL = {
	"TPRM": 176963.0,
}


def execute(sejak=SEJAK, restan_awal=None, sounding=True, sejak_sounding=None):
	"""Baca ulang Jumlah TBS Diterima September dengan rumus yang berlaku sekarang.

	`get_total_tbs` dulu menjumlahkan `netto_2` — netto sesudah potongan sortasi.
	Sejak commit 600f92ad (11 September 2026) yang dijumlahkan `netto`, yaitu
	bruto dikurangi tara tanpa potongan. Dokumen yang dibuat sebelum tanggal itu
	menyimpan angka basis lama dan tidak akan pernah menyusul sendiri: field ini
	cuma ditulis di `get_data`, yaitu waktu tombol Get Data ditekan.

	Selisihnya searah dan tidak kecil — DTBS-0066 menyimpan 323.733,47 sedangkan
	rumus sekarang memberi 335.190,00 untuk timbangan yang sama.

	Rantainya tidak disambung dari Agustus. Dokumen pertama tiap unit sejak
	`sejak` memakai angka RESTAN_AWAL, dan hari-hari sesudahnya baru merantai
	seperti biasa.

	Tiga fase:

	1. Restan Awal TBS per unit di RESTAN_AWAL. Submit-nya sekaligus membuat
	   Stock Reconciliation yang membawa saldo gudang TBS ke angka tetapan.
	2. hitung_ulang_rantai per unit sejak `sejak` — yang juga dipakai tombol
	   Hitung Ulang — membaca ulang TBS diterima, merantai restan dari patokan
	   tadi, lalu memposting ulang Stock Entry harian yang tidak cocok lagi.
	3. Rekap sounding CPO dan Palm Kernel lewat patch hitung_ulang_rekap_sounding.
	   Keduanya menyalin tbs olah dari Data TBS cuma waktu Get Data ditekan, jadi
	   OER dan KER netto-nya tertinggal di tbs olah lama sampai dibaca ulang.
	   Harus sesudah fase 2: kalau dibalik, yang tersalin masih angka lama.
	   Rentangnya ikut patch sounding, mulai 2 September — alasannya di sana —
	   jadi sounding 1 September tidak ikut. `sounding=False` melewatinya.

	Aman dijalankan ulang: patokan yang sudah ada, dokumen yang angkanya sudah
	cocok, dan STE yang sudah benar sama-sama dilewati. Dokumen batal tidak ikut.

	Rentang dan angka patokannya bisa ditimpa waktu menjalankan, misalnya
	`--kwargs "{'sejak': '2026-10-01', 'restan_awal': {'TPRM': 123456}, 'sejak_sounding': '2026-10-01'}"`.
	"""
	sejak = getdate(sejak)
	restan_awal = restan_awal if restan_awal is not None else RESTAN_AWAL

	for unit, qty in restan_awal.items():
		pastikan_patokan(unit, sejak, qty)

	units = frappe.get_all(
		DOCTYPE,
		filters={"docstatus": ("<", 2), "tanggal_produksi": (">=", sejak)},
		pluck="unit",
		distinct=True,
		order_by="unit asc",
		limit_page_length=0,
	)

	if not units:
		print("Tidak ada Data TBS sejak {0}, dilewati.".format(sejak))
		return

	for unit in units:
		print("== Data TBS unit {0} sejak {1}".format(unit, sejak))
		hasil = hitung_ulang_rantai(unit, sejak, lapor=lambda pesan: print("   " + pesan))

		if hasil.kembar:
			print("   Dilewati karena tanggalnya dipakai lebih dari satu dokumen: {0}.".format(
				", ".join(hasil.kembar)))
			print("   Batalkan yang berlebih dulu, lalu jalankan patch ini lagi.")

		print("   {0} dokumen, {1} angka berubah, {2} Stock Entry dibuat ulang.".format(
			hasil.dokumen, hasil.angka, hasil.ste))

	if sounding:
		hitung_ulang_rekap_sounding.execute(
			sejak=sejak_sounding or hitung_ulang_rekap_sounding.SEJAK
		)


def pastikan_patokan(unit, tanggal, qty):
	"""Submit Restan Awal TBS unit ini di tanggal itu, kecuali sudah ada.

	Patokan yang sudah ada tidak ditimpa walau angkanya beda: bisa jadi itu
	koreksi yang sengaja dibuat orang sesudah patch ini ditulis. Yang beda cuma
	dilaporkan.
	"""
	ada = frappe.db.get_value(
		PATOKAN,
		{"unit": unit, "tanggal": tanggal, "docstatus": ("<", 2)},
		["name", "restan_awal", "docstatus"],
		as_dict=True,
	)

	if ada:
		if ada.docstatus == 0:
			print("{0}: {1} masih draft, submit dulu lalu jalankan patch ini lagi.".format(unit, ada.name))
		elif abs(flt(ada.restan_awal) - flt(qty)) >= 0.01:
			print("{0}: {1} sudah menetapkan {2:,.2f}, bukan {3:,.2f} — yang dipakai angka {1}.".format(
				unit, ada.name, flt(ada.restan_awal), flt(qty)))
		return

	doc = frappe.new_doc(PATOKAN)
	doc.unit = unit
	doc.tanggal = tanggal
	doc.restan_awal = flt(qty)
	doc.keterangan = "Dibuat patch hitung_ulang_tbs_diterima_data_tbs."
	# Hitung ulangnya dijalankan patch ini sendiri, langsung, bukan diantrikan.
	doc.flags.lewati_hitung_ulang = True
	doc.insert(ignore_permissions=True)
	doc.submit()
	frappe.db.commit()

	print("{0}: {1} restan awal {2:,.2f} sejak {3}{4}.".format(
		unit, doc.name, flt(qty), tanggal,
		", Stock Reconciliation " + doc.stock_reconciliation if doc.stock_reconciliation
		else ", saldo gudang sudah pas"))
