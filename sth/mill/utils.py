import contextlib

import frappe
from frappe.utils import cint, flt, get_first_day

SEHARI = 24 * 3600


def hitung_jam_desimal(jam_mulai, jam_selesai):
	"""Selisih dua jam dalam satuan jam desimal.

	Shift yang melewati tengah malam (mis. 23:00 → 01:00) ditambah 24 jam supaya
	tidak jadi negatif. Kalau salah satu jam kosong, hasilnya 0 — bukan None —
	supaya aman dijumlahkan di SQL maupun Python.
	"""
	if not jam_mulai or not jam_selesai:
		return 0.0

	mulai = _ke_detik(jam_mulai)
	selesai = _ke_detik(jam_selesai)

	if mulai is None or selesai is None:
		return 0.0

	selisih = selesai - mulai
	if selisih < 0:
		selisih += SEHARI

	return round(selisih / 3600.0, 2)


def _ke_detik(nilai):
	"""Ubah nilai field Time jadi detik sejak tengah malam.

	Frappe mengembalikan Time sebagai timedelta, tapi lewat API atau import bisa
	datang sebagai string "HH:MM:SS" atau "HH:MM".
	"""
	if hasattr(nilai, "total_seconds"):
		return int(nilai.total_seconds())

	if hasattr(nilai, "hour"):
		return nilai.hour * 3600 + nilai.minute * 60 + getattr(nilai, "second", 0)

	bagian = str(nilai).strip().split(":")
	if not bagian or not bagian[0]:
		return None

	try:
		jam = int(bagian[0])
		menit = int(bagian[1]) if len(bagian) > 1 else 0
		detik = int(float(bagian[2])) if len(bagian) > 2 else 0
	except (TypeError, ValueError):
		frappe.log_error(
			"Jam tidak bisa dibaca: {0}".format(nilai), "hitung_jam_desimal"
		)
		return None

	return jam * 3600 + menit * 60 + detik


def set_total_jam_desimal(self, method=None):
	"""Isi total_jam_desimal dari jam_mulai/jam_selesai.

	Dipasang di server (bukan cuma di form) supaya dokumen yang masuk lewat API
	atau import ikut terisi — angka ini yang jadi basis alokasi HM Costing Mill.
	"""
	self.total_jam_desimal = hitung_jam_desimal(
		self.get("jam_mulai"), self.get("jam_selesai")
	)


@contextlib.contextmanager
def izinkan_stock_minus():
	"""Matikan sementara larangan stok minus, lalu kembalikan setelah selesai.

	Membatalkan penerimaan lama membuat stok di tanggal itu berkurang, padahal
	Delivery Note sesudahnya sudah terlanjur mengambil barangnya. Selama
	penggantinya belum dibuat, ERPNext melihat stok minus di masa depan dan
	menolak pembatalannya. Jendela minus itu tidak bisa dihindari dengan
	mengerjakan dokumennya satu per satu, karena yang divalidasi adalah keadaan
	sesudah tanggal itu, bukan urutan pengerjaannya.
	"""
	asal = cint(frappe.db.get_single_value("Stock Settings", "allow_negative_stock"))

	if not asal:
		set_allow_negative_stock(1)

	try:
		yield
	finally:
		# Pekerjaan dokumen yang gagal dibuang dulu, supaya yang ikut ter-commit
		# bersama pengembalian setelan cuma dokumen yang sudah tuntas. Di jalur
		# sukses ini tidak ada efeknya, semuanya sudah di-commit per dokumen.
		frappe.db.rollback()

		if not asal:
			set_allow_negative_stock(0)
			# Harus di-commit di sini juga: kalau pemanggilnya gagal, migrate
			# akan rollback, dan tanpa commit ini site tertinggal dengan stok
			# minus masih diizinkan.
			frappe.db.commit()


def set_allow_negative_stock(nilai):
	frappe.db.set_single_value("Stock Settings", "allow_negative_stock", nilai)
	frappe.clear_document_cache("Stock Settings", "Stock Settings")

	# get_single_value menyimpan hasilnya sepanjang request, dan itulah yang
	# dibaca is_negative_stock_allowed tiap kali SLE dibuat.
	value_cache = getattr(frappe.db, "value_cache", None)
	if value_cache:
		value_cache.pop("Stock Settings", None)


def buang_ste(doc):
	"""Batalkan dan hapus semua Stock Entry yang menunjuk dokumen ini."""
	for row in frappe.get_all("Stock Entry", filters={"references": doc.name}, fields=["name", "docstatus"]):
		ste = frappe.get_doc("Stock Entry", row.name)
		if ste.docstatus == 1:
			ste.cancel()
		ste.delete()


def buat_ulang_ste(doc):
	"""Buang Stock Entry dokumen ini, lalu buat ulang lewat create_ste-nya.

	Qty maupun tanggal Stock Entry tidak bisa diubah setelah submit, jadi satu-
	satunya cara membetulkannya adalah membatalkan yang lama, menghapusnya, dan
	membiarkan controller-nya membuat yang baru. Mengembalikan jumlah STE yang
	dibuat, supaya pemanggilnya bisa melaporkannya — create_ste boleh saja
	memutuskan tidak membuat apa-apa.
	"""
	buang_ste(doc)
	doc.create_ste()

	return frappe.db.count("Stock Entry", {"references": doc.name})


def buat_ulang_ste_sounding(doc, produksi):
	"""buat_ulang_ste untuk dokumen sounding, yang STE-nya cuma dibuat kalau ada produksi.

	Syaratnya harus sama persis dengan on_submit kedua doctype sounding, yaitu
	produksi lebih besar dari nol. Sebelumnya cuma menolak nol, sehingga sounding
	berproduksi minus — yang jumlahnya banyak di CPO, akibat stock awal atau
	pengiriman yang belum benar — malah dibuatkan Material Issue sebesar angka
	minusnya waktu patch tanggal dijalankan, padahal submit biasa tidak pernah
	membuatkan apa-apa untuk dokumen itu.
	"""
	if flt(produksi) <= 0:
		buang_ste(doc)
		return 0

	return buat_ulang_ste(doc)


def get_adjustment_stock(item_code, warehouse, unit, doctype, tanggal_proses, termasuk_tanggal_proses=False):
	"""Mutasi gudang yang bukan berasal dari sounding maupun pengiriman.

	Yang ikut dihitung Stock Ledger Entry item ini di gudang ini yang vouchernya
	bukan Stock Entry buatan dokumen sounding dan bukan Delivery Note / Purchase
	Receipt. Sisanya berarti koreksi manual — Stock Entry yang diketik sendiri
	atau Stock Reconciliation — dan itulah yang disebut adjustment di sini.

	Rentangnya dibatasi sejak tanggal proses sounding sebelumnya di unit yang
	sama. Tanpa batas bawah yang terhitung adalah tumpukan koreksi berbulan-bulan,
	padahal yang mau dijawab cuma "stock awal hari ini bergeser berapa gara-gara
	koreksi sejak sounding kemarin".

	Rentangnya setengah terbuka, dan ujung mana yang terbuka mengikuti apa yang
	sudah tercakup stock awal masing-masing dokumen. Sounding PK memakai saldo
	sebelum tanggal proses, jadi rentangnya [sounding sebelumnya, tanggal proses).
	Sounding CPO memakai saldo berjalan sehingga mutasi di tanggal prosesnya
	sendiri ikut, jadi rentangnya (sounding sebelumnya, tanggal proses].

	Dua-duanya harus setengah terbuka, bukan terbuka di kedua ujung: sounding
	dibuat harian, jadi rentang yang terbuka di kedua ujung selalu kosong dan
	koreksi yang diposting tepat di tanggal sounding sebelumnya tidak pernah
	terhitung sama sekali.
	"""
	if not (item_code and warehouse and tanggal_proses):
		return 0.0

	sebelumnya = frappe.db.sql("""
		select max(tanggal_proses) from `tab{doctype}`
		where unit = %(unit)s and docstatus < 2 and tanggal_proses < %(tanggal_proses)s
	""".format(doctype=doctype), {"unit": unit, "tanggal_proses": tanggal_proses})

	dari = (sebelumnya[0][0] if sebelumnya else None) or "1900-01-01"
	batas_bawah = ">" if termasuk_tanggal_proses else ">="
	batas_atas = "<=" if termasuk_tanggal_proses else "<"

	total = frappe.db.sql("""
		select coalesce(sum(sle.actual_qty), 0)
		from `tabStock Ledger Entry` sle
		left join `tabStock Entry` se
			on se.name = sle.voucher_no and sle.voucher_type = 'Stock Entry'
		where sle.is_cancelled = 0
			and sle.item_code = %(item_code)s and sle.warehouse = %(warehouse)s
			and sle.voucher_type not in ('Delivery Note', 'Purchase Receipt')
			and (se.reference_doctype is null or se.reference_doctype not like 'Sounding%%')
			and sle.posting_date {batas_bawah} %(dari)s
			and sle.posting_date {batas_atas} %(sampai)s
	""".format(batas_bawah=batas_bawah, batas_atas=batas_atas), {
		"item_code": item_code,
		"warehouse": warehouse,
		"dari": dari,
		"sampai": tanggal_proses,
	})

	return flt(total[0][0]) if total else 0.0


# Field tiap dokumen sounding yang dipakai menghitung rendemen rata-rata sebulan,
# plus field informasi tempat hasilnya disimpan. Nama doctype dan field masuk
# langsung ke SQL, jadi cuma yang terdaftar di sini yang boleh lewat.
RENDEMEN_BULANAN = {
	"Sounding Stock CPO di BST": {
		"produksi": "produksi_cpo",
		"tbs_olah": "tbs_olah",
		"sortasi": "potongan_sortasi",
		"target": "rata_rata_oer_bulanan",
	},
	"Sounding Stock Palm Kernel di Bunker Kernel": {
		"produksi": "produksi",
		"tbs_olah": "tbs_olah",
		"sortasi": "sortasi",
		"target": "rata_rata_ker_bulanan",
	},
}


def set_rata_rata_rendemen_bulanan(doc):
	"""Isi field informasi rata-rata rendemen sebulan di dokumen sounding.

	Caranya sama dengan rata-rata harga jual CPO di COGS Mill dan Kebun: yang
	dirata-rata bukan angka persen hariannya, tapi bahannya. Total produksi sejak
	awal bulan tanggal_proses sampai tanggal_proses dokumen ini dibagi total TBS
	olah pada rentang yang sama, dikali 100. Sama seperti rendemen harian, TBS olah
	di penyebut dikurangi potongan sortasi dulu — jadi ini tetap rendemen netto 2,
	cuma ditimbang tonasenya.

	Bedanya dengan rata-rata harian sederhana: hari yang tbs olahnya besar menarik
	angkanya lebih kuat, dan hari yang tidak mengolah TBS sama sekali tidak lagi
	ikut membagi. Hari yang produksinya nol atau minus tetap ikut, lewat pembilang.

	Sebulan, tapi berhenti di tanggal dokumennya sendiri — hari sesudahnya tidak
	ikut. Angkanya jadi rata-rata berjalan yang isinya cuma hal-hal yang sudah
	terjadi waktu dokumen itu dibuat, dan hasilnya tidak berubah lagi kalau
	dokumen ini dibuka sesudah sounding hari-hari berikutnya masuk. Itu juga yang
	bikin patch data lama masuk akal: dokumen diproses urut tanggal, dan
	rata-rata tiap dokumen cuma bergantung pada dokumen yang sudah dilewati
	patch, bukan pada dokumen di depannya yang belum dihitung ulang.

	Dipanggil dari validate maupun onload. Dari onload karena batas atasnya ikut
	tanggal_proses sendiri: waktu validate dokumen ini masih docstatus 0 sehingga
	tidak ikut rata-ratanya sendiri, dan sounding bertanggal mundur yang disubmit
	belakangan juga masih bisa menggeser angkanya.
	"""
	cfg = RENDEMEN_BULANAN[doc.doctype]
	doc.set(cfg["target"], 0)

	if not (doc.unit and doc.tanggal_proses):
		return

	row = frappe.db.sql("""
		select sum(coalesce(d.`{produksi}`, 0)),
			sum(coalesce(d.`{tbs_olah}`, 0) - coalesce(d.`{sortasi}`, 0))
		from `tab{doctype}` d
		where d.docstatus = 1 and d.unit = %(unit)s
			and d.tanggal_proses between %(dari)s and %(sampai)s
	""".format(
		produksi=cfg["produksi"],
		tbs_olah=cfg["tbs_olah"],
		sortasi=cfg["sortasi"],
		doctype=doc.doctype,
	), {
		"unit": doc.unit,
		"dari": get_first_day(doc.tanggal_proses),
		"sampai": doc.tanggal_proses,
	})

	if not (row and row[0]):
		return

	doc.set(cfg["target"], hitung_rendemen(row[0][0], row[0][1]))


def hitung_rendemen(produksi, penyebut):
	"""Rendemen persen dari total produksi dan total TBS olah netto 2.

	Penjaganya penyebut itu sendiri, bukan tbs olah kotornya: kalau seluruh TBS
	yang masuk kena potongan sortasi, penyebutnya nol dan pembagiannya error.
	Sama seperti hitung_produksi di dokumen soundingnya.
	"""
	penyebut = flt(penyebut)

	return flt(produksi) / penyebut * 100 if penyebut else 0.0
