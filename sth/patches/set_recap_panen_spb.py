import frappe

from sth.plantation.doctype.surat_pengantar_buah.surat_pengantar_buah import (
	set_recap_panen_in_details,
)


def execute(spb_names=None):
	"""Pasang recap_panen di baris detail SPB yang masih kosong.

	SPB yang masuk lewat API sebelum lookup recap_panen ada di sisi server
	tersimpan tanpa link ke Recap Panen by Blok, jadi janjangnya tidak pernah
	ikut terhitung sebagai transfered_janjang di recap-nya.

	Tanpa argumen (jalur migrate) semua SPB yang detailnya masih bolong ikut
	diproses. Untuk SPB tertentu, panggil dari bench console:

	    from sth.patches.set_recap_panen_spb import execute
	    execute(["SPB-00001", "SPB-00002"])
	"""
	names = _resolve_spb_names(spb_names)
	if not names:
		return

	touched_recaps = set()

	for name in names:
		touched_recaps.update(_fill_spb(name))

	_recalculate_recaps(touched_recaps)


def _resolve_spb_names(spb_names):
	if spb_names:
		if isinstance(spb_names, str):
			spb_names = [n.strip() for n in spb_names.split(",")]

		return [n for n in spb_names if n]

	# Baris yang blok + tanggal panennya ada tapi link recap-nya belum keisi.
	# Restan ikut dicari lewat kolomnya sendiri karena bisa bolong terpisah.
	rows = frappe.db.sql(
		"""
		SELECT DISTINCT parent
		FROM `tabSPB Timbangan Pabrik`
		WHERE parenttype = 'Surat Pengantar Buah'
			AND docstatus < 2
			AND (
				(IFNULL(blok, '') != '' AND panen_date IS NOT NULL AND IFNULL(recap_panen, '') = '')
				OR (IFNULL(blok_restan, '') != '' AND panen_date_restan IS NOT NULL AND IFNULL(recap_panen_restan, '') = '')
			)
		""",
		as_dict=True,
	)

	return [r.parent for r in rows]


def _fill_spb(name):
	"""Isi recap_panen satu SPB, kembalikan recap yang tersentuh.

	Ditulis per baris lewat db_set: SPB yang sudah submit tidak bisa di-save,
	dan patch ini memang cuma memasang link tanpa mengubah angka apa pun.
	"""
	doc = frappe.get_doc("Surat Pengantar Buah", name)

	before = {d.name: (d.recap_panen, d.recap_panen_restan) for d in doc.details}

	set_recap_panen_in_details(doc.details)

	touched_recaps = set()

	for d in doc.details:
		for fieldname, old in zip(("recap_panen", "recap_panen_restan"), before[d.name]):
			new = d.get(fieldname)

			if not new or new == old:
				continue

			frappe.db.set_value(
				"SPB Timbangan Pabrik", d.name, fieldname, new, update_modified=False
			)
			touched_recaps.add(new)

	return touched_recaps


def _recalculate_recaps(recap_names):
	"""Hitung ulang transfered_janjang recap yang baru dapat baris SPB.

	calculate_transfered_weight() melempar kalau totalnya melebihi jumlah
	janjang blok. Itu data yang memang perlu dilihat orang, jadi dicatat ke
	log lalu lanjut ke recap berikutnya, bukan menggagalkan seluruh patch.
	Throw-nya terjadi sebelum db_update, jadi tidak ada tulisan separuh jalan
	yang perlu di-rollback — dan rollback justru akan membuang link yang sudah
	terpasang untuk SPB sebelumnya.
	"""
	for recap_name in recap_names:
		try:
			frappe.get_doc("Recap Panen by Blok", recap_name).calculate_transfered_weight()
		except Exception:
			frappe.log_error(
				title="set_recap_panen_spb: gagal hitung ulang transfered_janjang",
				message=f"Recap Panen by Blok: {recap_name}\n\n{frappe.get_traceback()}",
			)
