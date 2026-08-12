import frappe

from sth.mill.utils import hitung_jam_desimal

DOCTYPES = (
	"Buku Kerja Mekanik",
	"Preventive Maintenance",
)


def execute():
	"""Isi total_jam_desimal dokumen lama.

	Angkanya dihitung ulang dari jam_mulai/jam_selesai, bukan disalin dari
	`total_jam` yang bertipe Data — isinya campur antara "3.5" dan "03:30:00"
	tergantung kapan dokumennya dibuat, jadi tidak bisa dipercaya sebagai angka.
	"""
	for doctype in DOCTYPES:
		if not frappe.db.has_column(doctype, "total_jam_desimal"):
			continue

		baris = frappe.get_all(
			doctype,
			filters={"jam_mulai": ["is", "set"], "jam_selesai": ["is", "set"]},
			fields=["name", "jam_mulai", "jam_selesai"],
			limit_page_length=0,
		)

		for row in baris:
			frappe.db.set_value(
				doctype,
				row.name,
				"total_jam_desimal",
				hitung_jam_desimal(row.jam_mulai, row.jam_selesai),
				update_modified=False,
			)
