import frappe

from sth.plantation.doctype.surat_pengantar_buah.surat_pengantar_buah import (
	get_recap_panen,
)


def execute(rekap_names=None):
	"""Pasang ulang recap_panen di baris detail Rekap Timbangan Panen yang masih draft.

	Link recap dibawa dari SPB saat detail ditarik, jadi kalau Recap Panen by
	Blok-nya berubah sesudah itu — BKM Panen dikoreksi, rekap kosong terhapus,
	blok pindah tanggal — draft-nya masih memegang nama lama atau kosong. Baris
	yang linknya sudah benar tidak disentuh.

	Sengaja hanya draft: dokumen yang sudah submit sudah menulis
	transfered_janjang dan BJR ke recap serta BKM-nya, jadi menukar link di sana
	bukan perbaikan link lagi tapi perubahan angka — itu harus lewat cancel.

	Tanpa argumen semua Rekap Timbangan Panen draft ikut diproses. Untuk
	dokumen tertentu, panggil dari bench console:

	    from sth.patches.set_recap_panen_rekap_timbangan import execute
	    execute(["RTP-00001", "RTP-00002"])
	"""
	names = _resolve_rekap_names(rekap_names)
	if not names:
		return {"diperiksa": 0, "diperbarui": 0, "tidak_ketemu": []}

	updated = 0
	not_found = []

	for name in names:
		u, nf = _fill_rekap(name)
		updated += u
		not_found.extend(nf)

	if not_found:
		frappe.log_error(
			title="set_recap_panen_rekap_timbangan: recap tidak ketemu",
			message="\n".join(not_found),
		)

	return {"diperiksa": len(names), "diperbarui": updated, "tidak_ketemu": not_found}


def _resolve_rekap_names(rekap_names):
	if rekap_names:
		if isinstance(rekap_names, str):
			rekap_names = [n.strip() for n in rekap_names.split(",")]

		return [n for n in rekap_names if n]

	# Semua draft yang punya baris dengan blok + tanggal panen. Baris yang
	# link-nya sudah benar disaring belakangan, karena "benar" hanya bisa
	# ditentukan setelah recap-nya dicari ulang.
	rows = frappe.db.sql(
		"""
		SELECT DISTINCT td.parent
		FROM `tabTimbangan Panen Details` td
		INNER JOIN `tabRekap Timbangan Panen` rt ON rt.name = td.parent
		WHERE rt.docstatus = 0
			AND IFNULL(td.blok, '') != ''
			AND td.panen_date IS NOT NULL
		""",
		as_dict=True,
	)

	return [r.parent for r in rows]


def _fill_rekap(name):
	"""Isi recap_panen satu Rekap Timbangan Panen, kembalikan (jumlah, catatan).

	Ditulis per baris lewat db_set supaya validate tidak ikut jalan: detail yang
	jumlah_janjang-nya masih 0 akan membuat calculate_janjang membagi nol, dan
	patch ini memang cuma memasang link tanpa mengubah angka apa pun.
	"""
	doc = frappe.get_doc("Rekap Timbangan Panen", name)

	updated = 0
	not_found = []

	for d in doc.details:
		if not (d.blok and d.panen_date):
			continue

		recap_panen = get_recap_panen(d.blok, d.panen_date).get("recap_panen")
		if not recap_panen:
			not_found.append(f"{name} baris {d.idx}: blok {d.blok} tanggal {d.panen_date}")
			continue

		if recap_panen == d.recap_panen:
			continue

		frappe.db.set_value(
			"Timbangan Panen Details", d.name, "recap_panen", recap_panen,
			update_modified=False
		)
		updated += 1

	return updated, not_found
