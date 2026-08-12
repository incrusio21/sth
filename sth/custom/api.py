import frappe
from frappe import _

# User yang dipakai sistem luar waktu mengirim dokumen lewat REST API. Dipakai
# untuk membedakan kiriman mesin dari input manusia.
USER_API = "api@sth.com"

# Mandor pada data BKM dari API kadang terkirim sebagai ID User, bukan Employee.
# Petakan ke NIK karyawan yang benar supaya link Employee-nya valid.
#
# Ditulis di sini, bukan dicari ke database, karena ID User sistem luar memang
# tidak tersimpan di mana pun di ERP — tidak ada field Employee yang memuatnya.
# Mandor baru harus ditambahkan ke daftar ini dan butuh deploy.
MANDOR_API_MAP = {
	"USR251015341": "1506012411940004",
	"USR251015035": "1206010909900006",
}

# Kegiatan pada kiriman BKM dari API datang sebagai kode induk (group), bukan kode
# kegiatan yang benar-benar dipakai dokumen. Petakan ke anak kegiatannya supaya
# Link-nya valid dan upah, premi, serta akunnya terambil dari master yang benar.
#
# Sengaja ditulis di sini, bukan ditelusuri lewat pohon Kegiatan: baru dua kode ini
# yang dikirim sistem luar dan masing-masing memang selalu jatuh ke satu anak yang
# sama. Kode induk baru harus ditambahkan ke daftar ini dan butuh deploy.
KEGIATAN_API_MAP = {
	"12660": "126600101",
	"12666": "126660101",
}


# Item pada tabel material kiriman BKM datang dengan kode milik sistem luar, bukan
# kode Item di ERP. Petakan supaya Link Item-nya valid dan Stock Entry-nya
# mengeluarkan barang yang benar.
#
# Sama seperti KEGIATAN_API_MAP, ditulis sebagai daftar karena pemetaannya tidak
# bisa diturunkan dari kodenya sendiri. Kode baru harus ditambahkan di sini dan
# butuh deploy.
ITEM_API_MAP = {
	"30202001": "30301013",
	"31101019": "30101009",
	"31201002": "30302011",
	"31201012": "30301001",
}


def fix_kegiatan_from_api(doc):
	"""Ganti kode kegiatan induk kiriman API dengan kode anak yang dituju.

	Hanya kode yang terdaftar di KEGIATAN_API_MAP yang diganti. Nilai lain
	dibiarkan apa adanya — input dari UI sudah memilih kegiatan non-group lewat
	`kegiatan_query`, jadi tidak ada yang perlu diterjemahkan di sana.

	Kalau kode anaknya ternyata belum ada di master Kegiatan, dokumen tetap
	ditolak validasi Link seperti biasa, dan pesannya menyebut kode anak itu —
	bukan kode induk yang memang tidak pernah ada sebagai kegiatan non-group.
	"""
	kegiatan = doc.get("kegiatan")
	if not kegiatan:
		return

	anak = KEGIATAN_API_MAP.get(str(kegiatan).strip())
	if anak:
		doc.kegiatan = anak


def fix_item_from_api(doc):
	"""Rapikan baris material kiriman API: kode itemnya, lalu nama barangnya.

	Hanya kode yang terdaftar di ITEM_API_MAP yang diganti; sisanya lewat apa
	adanya, sama seperti fix_kegiatan_from_api. Kode tak terdaftar yang ternyata
	bukan Item tetap ditolak validasi Link seperti biasa, dan pesannya menyebut
	kode mentah itu — jadi kode yang belum dipetakan langsung kelihatan.

	Dipanggil sebelum Stock Entry dibuat, karena create_ste_issue mengeluarkan
	barang memakai `item` baris ini apa adanya.

	`nama_barang` diisi dari master Item. Field itu tidak punya fetch_from dan
	sistem luar tidak pernah mengirimnya, jadi tanpa ini seluruh baris material
	dari API kosong namanya. Baris yang kodenya diterjemahkan selalu ditimpa —
	nama kiriman, kalau ada, menerangkan kode yang lama. Sisanya cuma diisi kalau
	memang masih kosong, supaya nama yang sengaja dikirim tidak tertimpa.

	Item yang tidak ketemu dibiarkan tanpa nama; validasi Link yang menolak
	dokumennya, dan pesannya menyebut kode itemnya sendiri.
	"""
	for baris in doc.get("material") or []:
		item = baris.get("item")
		if not item:
			continue

		pengganti = ITEM_API_MAP.get(str(item).strip())
		if pengganti:
			baris.item = pengganti

		if pengganti or not baris.get("nama_barang"):
			baris.nama_barang = frappe.db.get_value("Item", baris.item, "item_name")


def fix_mandor_from_api(doc):
	"""Isi `kode_mandor` (Link Employee) dari nilai `mandor` yang dikirim API.

	`mandor` sengaja bertipe Data, bukan Link: sistem luar mengirim ID User-nya
	sendiri dan payload itu tidak bisa diubah, jadi nilainya harus boleh masuk apa
	adanya tanpa divalidasi sebagai Employee. Employee sebenarnya disimpan terpisah
	di `kode_mandor`, dan itulah yang dibaca seluruh logika BKM.

	ID yang belum terdaftar di MANDOR_API_MAP tidak menggagalkan dokumen — dulu
	justru itu yang memblokir seluruh kiriman. `kode_mandor` dibiarkan kosong, dan
	kode mentahnya tetap terbaca di `mandor` untuk ditelusuri.
	"""
	if doc.get("kode_mandor"):
		return

	mandor = doc.get("mandor")
	if not mandor:
		return

	if mandor in MANDOR_API_MAP:
		doc.kode_mandor = MANDOR_API_MAP[mandor]
		return

	# dokumen lama dan input manusia mengirim NIK Employee di field yang sama
	if frappe.db.exists("Employee", mandor):
		doc.kode_mandor = mandor


def submit_after_insert(doc):
	"""Submit dokumen dari dalam hook after_insert.

	Hanya untuk dipanggil dari after_insert. submit() -> _save() ->
	check_if_latest() menyetel doc._action = "submit". Setelah after_insert
	selesai, insert() masih menjalankan run_post_save_methods() pada objek yang
	sama dan membaca _action tersebut, sehingga on_submit terpanggil untuk kedua
	kali. Turunkan _action kembali ke "save" supaya pass kedua itu hanya
	menjalankan on_update (yang sebelumnya juga sudah jalan dua kali, jadi bukan
	perubahan perilaku).

	Gejalanya dulu: BKM Panen dari API gagal dengan "List Blok already used"
	karena create_recap_panen_by_blok() jalan dua kali dan kena unique index
	(blok, company, posting_date) pada Recap Panen by Blok.
	"""
	doc.submit()
	doc._action = "save"

@frappe.whitelist()
def approve_api(self,method):
	if self.owner != USER_API:
		return

	# hook terpasang untuk semua doctype, lewati yang tidak submittable
	# (Employee Payment Log, Buku Kerja Mandor Premi, dll yang dibuat saat on_submit)
	if not self.meta.is_submittable or self.docstatus != 0:
		return

	submit_after_insert(self)