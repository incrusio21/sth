import frappe

# BKM yang field mandor-nya berubah dari Link Employee jadi Data
DOCTYPES = (
	"Buku Kerja Mandor Perawatan",
	"Buku Kerja Mandor Panen",
	"Buku Kerja Mandor Traksi",
)


def execute():
	"""Salin mandor lama ke kode_mandor.

	Sebelum ini `mandor` bertipe Link Employee, jadi seluruh nilai yang tersimpan
	pasti Employee yang sah. Sesudah ini `mandor` cuma menampung nilai mentah
	kiriman API dan Employee-nya pindah ke `kode_mandor` — tanpa disalin, dokumen
	lama kehilangan mandornya.

	ID User sistem luar yang sempat masuk sebelum pemetaan dipakai ikut
	diterjemahkan lewat MANDOR_API_MAP.
	"""
	from sth.custom.api import MANDOR_API_MAP

	for doctype in DOCTYPES:
		if not frappe.db.has_column(doctype, "kode_mandor"):
			continue

		baris = frappe.get_all(
			doctype,
			filters={
				"mandor": ["is", "set"],
				"kode_mandor": ["in", ["", None]],
			},
			fields=["name", "mandor"],
			limit_page_length=0,
		)

		for row in baris:
			kode = MANDOR_API_MAP.get(row.mandor, row.mandor)

			# yang tidak cocok Employee mana pun dibiarkan kosong; kode mentahnya
			# tetap terbaca di field mandor
			if not frappe.db.exists("Employee", kode):
				continue

			frappe.db.set_value(doctype, row.name, "kode_mandor", kode, update_modified=False)
