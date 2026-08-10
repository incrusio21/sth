import frappe

# User yang dipakai sistem luar waktu mengirim dokumen lewat REST API. Dipakai
# untuk membedakan kiriman mesin dari input manusia.
USER_API = "api@sth.com"

# Mandor pada data BKM dari API kadang terkirim sebagai ID User, bukan Employee.
# Petakan ke NIK karyawan yang benar supaya link Employee-nya valid.
MANDOR_API_MAP = {
	"USR251015341": "1506012411940004",
	"USR251015035": "1206010909900006",
}


def fix_mandor_from_api(doc):
	"""Ganti nilai mandor yang berupa ID User dengan NIK Employee-nya."""
	mandor = doc.get("mandor")
	if mandor in MANDOR_API_MAP:
		doc.mandor = MANDOR_API_MAP[mandor]


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