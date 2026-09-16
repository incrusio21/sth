import frappe
from frappe.utils import flt, getdate

from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import (
	EmptyStockReconciliationItemsError,
)
from erpnext.stock.utils import get_stock_balance

from sth.mill.doctype.data_tbs.data_tbs import (
	get_total_tbs,
	get_warehouse_tbs,
	posting_ulang_ste,
)

DOCTYPE = "Data TBS"

# Hanya September ke atas yang dibetulkan. Dokumen sebelumnya dibiarkan apa
# adanya beserta Stock Entry-nya, jadi periode yang sudah dilaporkan tidak ikut
# bergerak.
SEJAK = "2026-09-01"

# Restan awal yang ditetapkan untuk dokumen pertama tiap unit sejak SEJAK,
# menggantikan perantaian dari dokumen terakhir sebelum tanggal itu. Angkanya
# hasil hitungan di luar sistem, bukan turunan dokumen mana pun, jadi ditulis
# di sini supaya tercatat di git — bukan diketik di konsol waktu menjalankan.
RESTAN_AWAL = {
	"TPRM": 176963.0,
}

# Sebelum Stock Entry Data TBS hari itu, yang diposting pukul 23:59:59.
WAKTU_SEMAI = "00:00:00"

# None berarti ikut default company gudangnya: stock_adjustment_account dan
# cost_center. Isi di sini kalau akuntansi mau selisihnya mendarat di tempat lain.
AKUN_SELISIH = None
COST_CENTER = None


def execute(sejak=SEJAK, restan_awal=None):
	"""Baca ulang Jumlah TBS Diterima September dengan rumus yang berlaku sekarang.

	`get_total_tbs` dulu menjumlahkan `netto_2` — netto sesudah potongan sortasi.
	Sejak commit 600f92ad (11 September 2026) yang dijumlahkan `netto`, yaitu
	bruto dikurangi tara tanpa potongan. Dokumen yang dibuat sebelum tanggal itu
	menyimpan angka basis lama dan tidak akan pernah menyusul sendiri: field ini
	cuma ditulis di `get_data`, yaitu waktu tombol Get Data ditekan, dan tidak
	pernah dihitung ulang di `validate` seperti halnya restan awal.

	Selisihnya searah dan tidak kecil — DTBS-0066 menyimpan 323.733,47 sedangkan
	rumus sekarang memberi 335.190,00 untuk timbangan yang sama.

	Sekalian ikut terbawa: perubahan Timbangan yang terjadi sesudah Get Data
	ditekan. DTBS-0068 misalnya menyimpan angka yang masih memuat TBG-11180,
	timbangan yang dibatalkan dua jam sesudah dokumennya disimpan.

	Restan awalnya ikut dirantai ulang karena Jumlah TBS Diterima masuk ke Grand
	Total TBS, yang membagi diri jadi tbs olah, tbs restan, dan tbs loading ramp,
	dan Total TBS Restan-nya jadi restan awal hari berikutnya.

	Rantainya tidak disambung dari Agustus. Dokumen pertama tiap unit sejak
	`sejak` memakai angka RESTAN_AWAL yang ditetapkan sendiri, dan hari-hari
	sesudahnya baru merantai seperti biasa.

	Tiga fase: angka dokumennya, lalu Stock Reconciliation yang membawa saldo
	gudang ke angka tetapan itu, lalu posting ulang Stock Entry harian yang qty
	atau arahnya jadi tidak cocok lagi. Dipisah supaya kalau salah satunya
	tertahan periode akuntansi yang sudah tutup, yang sudah lewat tetap benar.

	Aman dijalankan ulang: dokumen yang angkanya sudah cocok, saldo gudang yang
	sudah pas, dan STE yang sudah benar sama-sama dilewati. Dokumen batal tidak
	ikut.

	Rentang dan angka semaiannya bisa ditimpa waktu menjalankan, misalnya
	`--kwargs "{'sejak': '2026-10-01', 'restan_awal': {'TPRM': 123456}}"`.
	"""
	sejak = getdate(sejak)
	restan_awal = restan_awal if restan_awal is not None else RESTAN_AWAL

	dokumen = frappe.get_all(
		DOCTYPE,
		filters={"docstatus": ("<", 2), "tanggal_produksi": (">=", sejak)},
		fields=["name", "unit", "tanggal_produksi"],
		order_by="unit asc, tanggal_produksi asc, creation asc",
		limit_page_length=0,
	)

	if not dokumen:
		print("Tidak ada Data TBS sejak {0}, dilewati.".format(sejak))
		return

	kembar = cari_kembar(dokumen)
	laporkan_kembar(kembar)

	dikerjakan = [row for row in dokumen if kunci(row) not in kembar]

	diperbaiki = hitung_ulang_dokumen(dokumen, kembar, restan_awal)
	print("{0} dari {1} Data TBS sejak {2} dibaca ulang Jumlah TBS Diterima-nya.".format(
		diperbaiki, len(dikerjakan), sejak))

	semai_stok(dokumen, sejak, restan_awal)

	posting_ulang_ste(dikerjakan, lapor=print)


def kunci(row):
	return (row.unit, str(row.tanggal_produksi))


def cari_kembar(dokumen):
	"""unit + tanggal yang punya lebih dari satu dokumen hidup.

	Hari kembar tidak boleh ikut dibaca ulang. `get_total_tbs` menjumlahkan
	seluruh timbangan sehari penuh tanpa tahu dokumen mana yang seharusnya
	memikulnya, jadi dua dokumen di hari yang sama akan sama-sama diberi total
	penuh dan hari itu masuk dua kali ke rantai restan.

	Dokumen seperti ini tidak bisa dibuat lagi — `validate_duplikat` menolaknya —
	tapi yang telanjur ada sejak sebelum penjagaan itu masih tertinggal. Mana
	yang harus dibatalkan adalah keputusan orang, bukan tebakan patch.
	"""
	hitung = {}

	for row in dokumen:
		hitung.setdefault(kunci(row), []).append(row.name)

	return {k: v for k, v in hitung.items() if len(v) > 1}


def laporkan_kembar(kembar):
	if not kembar:
		return

	print("Hari dengan lebih dari satu Data TBS — dilewati, angkanya dibiarkan apa adanya:")
	for (unit, tanggal), nama in sorted(kembar.items(), key=lambda item: item[0][1]):
		print("  {0} {1}: {2}".format(unit, tanggal, ", ".join(nama)))
	print("  Batalkan yang berlebih dulu, lalu jalankan patch ini lagi.")


def hitung_ulang_dokumen(dokumen, kembar, restan_awal):
	"""Isi ulang TBS diterima tiap dokumen, lalu rantai restan awalnya per unit."""
	restan = dict(restan_awal)
	diperbaiki = 0

	for row in dokumen:
		doc = frappe.get_doc(DOCTYPE, row.name)

		if kunci(row) in kembar:
			# Dilewati, tapi rantainya tetap diteruskan dari angka tersimpannya:
			# hari sesudahnya tidak boleh ikut hilang cuma karena hari ini kembar.
			restan[doc.unit] = flt(doc.total_tbs_restan)
			continue

		# Dibulatkan dulu sebelum dibanding: nilai yang dibaca dari kolom decimal
		# selalu beda di digit terakhir dari hasil hitungan float.
		sebelum = angka_turunan(doc)

		# flt: get_total_tbs memulangkan None kalau tidak ada timbangan sama
		# sekali di hari itu — SUM atas nol baris itu NULL, bukan 0.
		doc.jumlah_tbs_diterima = flt(get_total_tbs(doc.tanggal_produksi, doc.unit))
		doc.jumlah_tbs_restan = flt(restan.get(doc.unit, 0))
		doc.calculate_totals()
		restan[doc.unit] = flt(doc.total_tbs_restan)

		if angka_turunan(doc) == sebelum:
			continue

		# db_update, bukan save: dokumennya sudah disubmit dan yang diubah cuma
		# angka turunan yang seluruhnya read only di form.
		doc.db_update()
		diperbaiki += 1

	frappe.db.commit()

	return diperbaiki


def angka_turunan(doc):
	# Presisi field tidak dipakai: total_tbs_restan presisinya 0 supaya tampil
	# bulat di form, padahal selisih setengah kilo tetap harus ikut dibetulkan.
	return tuple(flt(doc.get(field), 3) for field in (
		"jumlah_tbs_diterima", "jumlah_tbs_restan", "grand_total_tbs",
		"berat_rata_rata_tbs", "tbs_olah", "tbs_restan", "tbs_loading_ramp",
		"total_tbs_restan",
	))


def semai_stok(dokumen, sejak, restan_awal):
	"""Bawa saldo gudang TBS ke restan tetapan, lewat Stock Reconciliation.

	Stock Entry Data TBS cuma memposting selisih Total TBS Restan dikurangi
	restan awal dokumen itu sendiri, yaitu pergerakan hari itu saja. Rangkaian
	selisih itu bersambung dengan saldo gudang hanya selama restan awal dirantai
	dari dokumen sebelumnya — dan menetapkan restan awal sendiri memutusnya.

	Yang dipakai Stock Reconciliation, bukan Material Receipt sebesar langkahnya,
	karena yang ditetapkan user itu saldo, bukan pergerakan: rekonsiliasi
	mendarat tepat di angka tetapan berapa pun isi buku stok sebelumnya. Itu juga
	yang membuat fase ini aman dijalankan ulang — kalau saldonya sudah pas,
	ERPNext menolaknya sebagai dokumen tanpa baris dan kita lewati.

	Penilaiannya tidak ikut digeser: valuation_rate diisi rate yang berlaku
	persis sebelum saat ini, jadi yang berubah cuma kuantitas.
	"""
	item = frappe.db.get_value("Item", {"tipe_barang": "TBS"})
	if not item:
		print("Item ber-tipe_barang TBS tidak ada, semai stok dilewati.")
		return

	unit_terpakai = []
	for row in dokumen:
		if row.unit not in unit_terpakai:
			unit_terpakai.append(row.unit)

	for unit in unit_terpakai:
		if unit not in restan_awal:
			continue

		gudang = get_warehouse_tbs(unit)
		if not gudang:
			print("{0}: gudang ber-warehouse_category TBS tidak ada, dilewati.".format(unit))
			continue

		tetapan = flt(restan_awal[unit])
		saldo, rate = get_stock_balance(
			item, gudang, sejak, WAKTU_SEMAI, with_valuation_rate=True
		)

		print("{0}: saldo {1} per {2} {3} = {4:,.2f}; ditetapkan {5:,.2f} (langkah {6:+,.2f}).".format(
			unit, gudang, sejak, WAKTU_SEMAI, flt(saldo), tetapan, tetapan - flt(saldo)))

		if abs(tetapan - flt(saldo)) < 0.01:
			print("   Saldo sudah pas, tidak ada rekonsiliasi yang dibuat.")
			continue

		nama = buat_rekonsiliasi(unit, gudang, item, tetapan, rate, sejak)
		if nama:
			print("   Stock Reconciliation {0} dibuat.".format(nama))

	frappe.db.commit()


def buat_rekonsiliasi(unit, gudang, item, qty, rate, sejak):
	company = frappe.db.get_value("Warehouse", gudang, "company")

	sr = frappe.new_doc("Stock Reconciliation")
	sr.purpose = "Stock Reconciliation"
	sr.company = company
	sr.unit = unit
	sr.set_posting_time = 1
	sr.posting_date = sejak
	sr.posting_time = WAKTU_SEMAI
	sr.expense_account = AKUN_SELISIH or frappe.db.get_value(
		"Company", company, "stock_adjustment_account")
	sr.cost_center = COST_CENTER or frappe.db.get_value("Company", company, "cost_center")

	sr.append("items", {
		"item_code": item,
		"warehouse": gudang,
		"qty": flt(qty),
		"valuation_rate": flt(rate),
	})

	# Pesan "tidak ada yang berubah" dari ERPNext dibuang supaya tidak menempel
	# di log dan tampil seolah patch-nya gagal.
	batas_pesan = len(frappe.local.message_log)
	try:
		sr.insert(ignore_permissions=True)
		sr.submit()
	except EmptyStockReconciliationItemsError:
		del frappe.local.message_log[batas_pesan:]
		print("   ERPNext menilai tidak ada yang berubah, rekonsiliasi batal dibuat.")
		return None

	return sr.name
