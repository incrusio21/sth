import frappe
from frappe.utils import cint, flt

# Kolom lama di level dokumen yang isinya turun jadi satu baris Detail RKH Kegiatan.
KOLOM_LAMA = (
	"kegiatan", "blok", "batch", "target_volume", "qty_tenaga_kerja",
	"kategori_kegiatan", "tipe_kegiatan", "is_bibitan", "volume_basis",
	"rupiah_basis", "kegiatan_amount", "voucher_type", "voucher_no",
)


def execute():
	"""Pindahkan kegiatan Rencana Kerja Harian dari level dokumen ke tabel barisnya.

	Satu RKH lama memuat tepat satu kegiatan, jadi tiap dokumen menghasilkan satu
	baris. Dokumen yang sudah punya baris dilewati, dan kolom lamanya dikosongkan
	begitu barisnya jadi — dua-duanya membuat patch ini aman diulang.

	Dokumen yang sudah disubmit ikut dipindah. Barisnya disisipkan lewat db_insert,
	bukan save(), supaya tidak ada validate maupun on_submit yang jalan ulang di
	dokumen yang jurnalnya sudah ada.
	"""
	if not frappe.db.has_column("Rencana Kerja Harian", "kegiatan"):
		# kolom lamanya sudah hilang dari tabel, berarti tidak ada yang perlu dipindah
		return

	sudah_punya_baris = set(frappe.db.sql_list("""
		SELECT DISTINCT parent
		FROM `tabDetail RKH Kegiatan`
		WHERE parenttype = 'Rencana Kerja Harian'
	"""))

	dokumen = frappe.db.sql("""
		SELECT name, docstatus, owner, modified_by, creation, modified, {kolom}
		FROM `tabRencana Kerja Harian`
		WHERE IFNULL(kegiatan, '') != ''
		ORDER BY creation
	""".format(kolom=", ".join(KOLOM_LAMA)), as_dict=True)

	dipindah = 0

	for doc in dokumen:
		if doc.name not in sudah_punya_baris:
			_buat_baris(doc)
			dipindah += 1

		_kosongkan_kolom_lama(doc)

	frappe.db.commit()
	print("Rencana Kerja Harian dipindah ke tabel kegiatan: {}".format(dipindah))


def _buat_baris(doc):
	# Panen dibayar per volume, sisanya per orang — aturan yang sama dipakai
	# update_rate_or_qty_value waktu menghitung baris baru.
	qty = flt(doc.target_volume) if doc.tipe_kegiatan == "Panen" else cint(doc.qty_tenaga_kerja)

	baris = frappe.new_doc("Detail RKH Kegiatan")
	baris.update({
		"kegiatan": doc.kegiatan,
		"kategori_kegiatan": doc.kategori_kegiatan,
		"tipe_kegiatan": doc.tipe_kegiatan,
		"is_bibitan": cint(doc.is_bibitan),
		"blok": doc.blok,
		"batch": doc.batch,
		"target_volume": flt(doc.target_volume),
		"qty_tenaga_kerja": cint(doc.qty_tenaga_kerja),
		# rincian laki-laki/perempuan tidak pernah ada di dokumen lama; dibiarkan nol
		# supaya qty_tenaga_kerja yang tercatat tidak ikut berubah waktu disimpan lagi
		"jumlah_tk_laki_laki": 0,
		"jumlah_tk_perempuan": 0,
		"volume_basis": flt(doc.volume_basis),
		"rupiah_basis": flt(doc.rupiah_basis),
		"qty": qty,
		"rate": flt(doc.rupiah_basis),
		"amount": flt(doc.kegiatan_amount),
		"voucher_type": doc.voucher_type,
		"voucher_no": doc.voucher_no,
	})

	baris.parent = doc.name
	baris.parenttype = "Rencana Kerja Harian"
	baris.parentfield = "kegiatan_detail"
	baris.idx = 1
	# barisnya harus seragam dengan induknya, supaya laporan yang menyaring
	# docstatus tidak melihat baris draft menempel di dokumen yang sudah disubmit
	baris.docstatus = cint(doc.docstatus)
	baris.owner = doc.owner
	baris.modified_by = doc.modified_by
	baris.creation = doc.creation
	baris.modified = doc.modified

	baris.db_insert()

	frappe.db.set_value("Rencana Kerja Harian", doc.name, {
		"total_luas": flt(doc.target_volume),
		"total_tenaga_kerja": cint(doc.qty_tenaga_kerja),
		"total_tk_laki_laki": 0,
		"total_tk_perempuan": 0,
		"kegiatan_detail_amount": flt(doc.kegiatan_amount),
	}, update_modified=False)


def _kosongkan_kolom_lama(doc):
	"""Lepas isi kolom lama supaya tidak ada dua sumber untuk angka yang sama.

	Kolomnya sendiri tetap tinggal di tabel — Frappe memang tidak pernah menghapus
	kolom — tapi isinya sudah tidak dibaca siapa pun lagi. Meninggalkannya terisi
	mengundang kejadian seperti `kode_kegiatan` dulu: kolom sisa yang masih ikut
	terbaca query lama dan diam-diam menyaring apa-apa.
	"""
	frappe.db.sql("""
		UPDATE `tabRencana Kerja Harian`
		SET kegiatan = NULL, blok = NULL, batch = NULL, kategori_kegiatan = NULL,
			tipe_kegiatan = NULL, voucher_type = NULL, voucher_no = NULL,
			target_volume = 0, qty_tenaga_kerja = 0, is_bibitan = 0,
			volume_basis = 0, rupiah_basis = 0, kegiatan_amount = 0
		WHERE name = %s
	""", doc.name)
