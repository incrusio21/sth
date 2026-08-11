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


def fix_mandor_from_api(doc):
	"""Ganti nilai mandor yang berupa ID User dengan NIK Employee-nya.

	Dipanggil dari before_insert, jadi penggantiannya sudah selesai sebelum link
	Employee divalidasi.

	ID yang belum terdaftar ditolak dengan pesannya sendiri. Tanpa itu yang muncul
	cuma LinkValidationError "Could not find Mandor: USR..." yang tidak memberi
	petunjuk bahwa yang kurang adalah entri di MANDOR_API_MAP.
	"""
	mandor = doc.get("mandor")
	if not mandor:
		return

	if mandor in MANDOR_API_MAP:
		doc.mandor = MANDOR_API_MAP[mandor]
		return

	# input manusia sudah dijaga link field-nya sendiri; yang diperiksa cuma
	# kiriman mesin, yang nilainya tidak bisa dikoreksi lewat form
	if doc.owner != USER_API:
		return

	if frappe.db.exists("Employee", mandor):
		return

	frappe.throw(
		_("Mandor {0} belum dipetakan ke NIK karyawan, dan tidak ada Employee dengan "
		  "kode itu. Tambahkan pemetaannya di MANDOR_API_MAP pada sth/custom/api.py — "
		  "ID User sistem luar tidak tersimpan di ERP, jadi tidak bisa dicari sendiri."
		  ).format(frappe.bold(mandor)),
		title=_("Mandor Belum Dipetakan")
	)


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